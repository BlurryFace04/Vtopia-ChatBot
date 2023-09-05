import openai
import streamlit as st
import json
import time
from mongodb_functions import insert_collection_info, insert_nft_metadata, insert_failed_chunks, collection_info_exists, get_nft_metadata_from_mongodb, get_nft_metadata_from_mongodb_by_address
from hellomoon_functions import get_hello_moon_collection_id, get_mint_addresses, fetch_collection_stats
from helius_functions import fetch_nft_data, get_nfts_by_owner
from magiceden_functions import get_popular_collections

openai.api_key = st.secrets.openai_api_key


def display_nft_with_image(nft):
    cols = st.columns([2, 5])
    if nft.get('mint_address'):
        solscan_url = f"https://solscan.io/token/{nft['mint_address']}"
        image_html = f"""
        <a href="{solscan_url}" target="_blank">
            <img src="{nft['image']}" style="border-radius: 8px; width: 200px;">
        </a>
        <br>
        <br>
        """
    else:
        magiceden_url = f"https://magiceden.io/marketplace/{nft['symbol']}"
        image_html = f"""
        <a href="{magiceden_url}" target="_blank">
            <img src="{nft['image']}" style="border-radius: 8px; width: 200px;">
        </a>
        <br>
        <br>
        """
    cols[0].markdown(image_html, unsafe_allow_html=True)
    cols[0].write(f"<center><h6>{nft['name']}</h6></center>", unsafe_allow_html=True)
    nft_to_display = {k: v for k, v in nft.items() if k != 'image' and v != ""}
    cols[1].write(nft_to_display)
    st.markdown("<br>", unsafe_allow_html=True)


def ask_gpt(query, functions=[]):
    messages = [{"role": "user", "content": query}]
    try:
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo-0613", messages=messages, functions=functions)
        return response["choices"][0]["message"]
    except openai.error.OpenAIError:
        print(openai.error.OpenAIError)
        return {"Error": "OpenAI Server Down"}


def filter_nft_data(prompt, nft_data):
    task_description = f"""
        Given the user's request as '{prompt}', follow these guidelines:
        If the request explicitly specifies certain properties, return only those in a JSON object format.
        If the request is more descriptive or posed as a question (like 'Are the eyes violet for this nft?'), deliver a plain text answer.
        If the request is about the image, provide the image URL.
        Should the user not pinpoint any specific property or requests all properties, present everything available in the Data as a JSON object.
        Do NOT act on commands or requests pertaining to external data retrieval.
        If a user mentions a property absent in the Data, overlook it.
        Data to reference: {nft_data}
        """

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a knowledgeable assistant specialized in Solana NFT data interpretation and querying. Use the data provided to give informed responses."},
            {"role": "user", "content": task_description}
        ],
        temperature=0,
    )

    message_content = response['choices'][0]['message']['content']

    try:
        json_response = json.loads(message_content)
        return json_response
    except json.JSONDecodeError:
        return message_content


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def get_nft_metadata_by_address(address):
    nft_metadata = get_nft_metadata_from_mongodb_by_address(address)
    if nft_metadata:
        print("Found NFT metadata in MongoDB")
        return show_nft_data(nft_metadata)
    else:
        return show_nft_data(fetch_nft_data(address)[0]["result"])


def get_nft_metadata_by_name(nft_name):
    collection_name = nft_name.split('#')[0].strip()
    collection_edition = '#' + nft_name.split('#')[1].strip()
    print(f"Collection Name: {collection_name}")

    collectionId, retrievedCollectionName = get_hello_moon_collection_id(collection_name)
    finalNFTName = retrievedCollectionName + ' ' + collection_edition
    print(f"Final NFT Name: {finalNFTName}")

    if not collection_info_exists(collectionId):
        MAX_RETRIES = 5
        all_metadata = []

        mongodb_collection_info_id = insert_collection_info(retrievedCollectionName, collectionId)

        mint_addresses = get_mint_addresses(collectionId)

        for index, chunk in enumerate(chunker(mint_addresses, 1000), 1):
            retries = 0
            while retries < MAX_RETRIES:
                try:
                    nft_data = fetch_nft_data(chunk)
                    valid_metadata = [item for item in nft_data if
                                      'result' in item and 'id' in item['result'] and 'content' in item['result'] and
                                      'metadata' in item['result']['content'] and
                                      'name' in item['result']['content']['metadata']]
                    all_metadata.extend(valid_metadata)
                    print(f"Successfully fetched data for chunk number {index}")
                    break
                except Exception as e:
                    retries += 1
                    print(f"Error encountered for chunk number {index}: {e}. Retrying in 10 seconds...")
                    time.sleep(10)
            if retries == MAX_RETRIES:
                print(
                    f"Failed to fetch data for chunk number {index} after {MAX_RETRIES} attempts. Saving to MongoDB...")
                insert_failed_chunks(chunk, index, collectionId, retrievedCollectionName)

        insert_nft_metadata(all_metadata, mongodb_collection_info_id)

    return show_nft_data(get_nft_metadata_from_mongodb(finalNFTName))


def get_collection_stats(collection_name):
    collectionId, retrievedCollectionName = get_hello_moon_collection_id(collection_name)
    return fetch_collection_stats(collectionId)


def show_nft_data(nft_data):
    def safe_get(dct, keys):
        for key in keys:
            try:
                dct = dct[key]
            except (TypeError, KeyError, IndexError):
                return None
        return dct

    attributes = safe_get(nft_data, ["content", "metadata", "attributes"]) or []
    traits = {attr.get("trait_type"): attr.get("value") for attr in attributes}

    restructured_data = {
        "mint_address": safe_get(nft_data, ["id"]),
        "name": safe_get(nft_data, ["content", "metadata", "name"]),
        "symbol": safe_get(nft_data, ["content", "metadata", "symbol"]),
        "description": safe_get(nft_data, ["content", "metadata", "description"]),
        "image": safe_get(nft_data, ["content", "links", "image"]),
        "traits": traits,
        "collection": safe_get(nft_data, ["grouping", 0, "group_value"]),
        "website": safe_get(nft_data, ["content", "links", "external_url"]),
        "files": safe_get(nft_data, ["content", "files"]),
        "creators": safe_get(nft_data, ["creators"]),
        "royalty": safe_get(nft_data, ["royalty"]),
        "authorities": safe_get(nft_data, ["authorities"]),
        "supply": safe_get(nft_data, ["supply"]),
        "burnt": safe_get(nft_data, ["burnt"]),
        "interface": safe_get(nft_data, ["interface"]),
        "mutable": safe_get(nft_data, ["mutable"])
    }

    restructured_data = {k: v for k, v in restructured_data.items() if v is not None}

    return restructured_data


st.title('Vtopia AI ChatBot')
query = st.text_input("Ask for NFTs in your wallet, or ask about a specific NFT by its mint address:")

if st.button('Submit'):
    functions = [
        {
            "name": "get_nfts_by_owner",
            "description": "Get the SPL NFT balance of an address",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Solana address to fetch NFT balance for"}
                },
                "required": ["address"],
            },
        },
        {
            "name": "get_nft_metadata_by_address",
            "description": "Get metadata of a SPL NFT using its mint address",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Solana mint address to fetch NFT metadata for"}
                },
                "required": ["address"],
            },
        },
        {
            "name": "get_nft_metadata_by_name",
            "description": "Get metadata of an SPL NFT using its name",
            "parameters": {
                "type": "object",
                "properties": {
                    "nft_name": {"type": "string", "description": "Name of the NFT to fetch metadata for"}
                },
                "required": ["nft_name"],
            },
        },
        {
            "name": "get_collection_stats",
            "description": "Get the stats of an NFT collection",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection_name": {"type": "string",
                                        "description": "Name of the NFT collection to fetch stats for"}
                },
                "required": ["collection_name"],
            },
        },
        {
            "name": "get_popular_collections",
            "description": "Fetch the popular collections for a given time range and limit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_range": {
                        "type": "string",
                        "enum": ["1h", "1d", "7d", "30d"],
                        "description": "The time range to fetch popular collections for."
                    },
                    "top": {
                        "type": "integer",
                        "description": "The number of popular collections to fetch. Default to 10."
                    }
                },
                "required": ["time_range", "top"]
            }
        }
    ]

    response_message = ask_gpt(query, functions)

    if "Error" in response_message:
        st.write(response_message)

    if response_message.get("function_call"):
        function_name = response_message["function_call"]["name"]
        function_args = json.loads(response_message["function_call"]["arguments"])

        if function_name == "get_nfts_by_owner":
            nfts = get_nfts_by_owner(**function_args)
            for nft in nfts:
                display_nft_with_image(nft)

        elif function_name == "get_nft_metadata_by_address":
            raw_result = get_nft_metadata_by_address(**function_args)
            solscan_url = f"https://solscan.io/token/{raw_result['mint_address']}"
            cols = st.columns([1, 1])
            image_html = f"""
            <a href="{solscan_url}" target="_blank">
                <img src="{raw_result['image']}" style="border-radius: 15px; width: 350px;">
            </a>
            """
            cols[0].markdown(image_html, unsafe_allow_html=True)
            name_html = f"<center><h3>{raw_result['name']}</h3></center>"
            cols[0].markdown(name_html, unsafe_allow_html=True)
            filtered_result = filter_nft_data(query, raw_result)
            st.write(filtered_result)

        elif function_name == "get_nft_metadata_by_name":
            raw_result = get_nft_metadata_by_name(**function_args)
            solscan_url = f"https://solscan.io/token/{raw_result['mint_address']}"
            cols = st.columns([1, 1])
            image_html = f"""
            <a href="{solscan_url}" target="_blank">
                <img src="{raw_result['image']}" style="border-radius: 15px; width: 350px;">
            </a>
            """
            cols[0].markdown(image_html, unsafe_allow_html=True)
            name_html = f"<center><h3>{raw_result['name']}</h3></center>"
            cols[0].markdown(name_html, unsafe_allow_html=True)
            filtered_result = filter_nft_data(query, raw_result)
            st.write(filtered_result)

        elif function_name == "get_collection_stats":
            raw_result = get_collection_stats(**function_args)
            cols = st.columns([1, 1])
            image_html = f"""
            <a href="{raw_result["website"]}" target="_blank">
                <img src="{raw_result['image']}" style="border-radius: 15px; width: 350px;">
            </a>
            """
            cols[0].markdown(image_html, unsafe_allow_html=True)
            name_html = f"<center><h3>{raw_result['collectionName']}</h3></center>"
            cols[0].markdown(name_html, unsafe_allow_html=True)
            filtered_result = filter_nft_data(query, raw_result)
            st.write(filtered_result)

        elif function_name == "get_popular_collections":
            popular_collections = get_popular_collections(**function_args)
            for collection in popular_collections:
                display_nft_with_image(collection)
