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
    try:
        collection_edition = '#' + nft_name.split('#')[1].strip()
    except:
        return {"Error": "Specify the edition of the NFT you are looking for, or if you are looking for a collection, specify the word 'collection' somewhere in the prompt'"}
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


st.set_page_config(page_title="Vtopia SeraAI", page_icon="white-logo.png")

col1, col2, col3, col4 = st.columns([2.3, 1.1, 5, 1.5])
col2.image('white-logo.png', width=80)
col3.title("Vtopia SeraAI")

# Sidebar title
st.sidebar.title("Vtopia SeraAI Features")

# Introduction
st.sidebar.markdown("Welcome to **Vtopia SeraAI**! Here's a quick guide on how to interact with the available features:")

# Feature 1: Ask for NFTs in your wallet
st.sidebar.markdown("### 1. NFTs in Your Wallet")
st.sidebar.markdown("🔍 Query the NFTs present in your Solana wallet.")
st.sidebar.markdown("**Example:**")
st.sidebar.code("'Show me the NFTs in my wallet: [Your Wallet Address]'")

# Feature 2: Ask about a specific NFT by its mint address
st.sidebar.markdown("### 2. NFT Details by Mint Address")
st.sidebar.markdown("🖼 Get detailed information of a specific NFT using its mint address.")
st.sidebar.markdown("**Example:**")
st.sidebar.code("'Tell me about the NFT with mint address: [Mint Address]'")
st.sidebar.caption('You can ask it to query only specific properties of the NFT as well.')

# Feature 3: Ask about an NFT by its name
st.sidebar.markdown("### 3. NFT Details by Name")
st.sidebar.markdown("🏷 Query details of an NFT by its name.")
st.sidebar.markdown("**Example:**")
st.sidebar.code("'Tell me about the NFT named: [NFT Name]'")
st.sidebar.caption('You can ask it to query only specific properties of the NFT as well.')

# Feature 4: Get stats of an NFT collection
st.sidebar.markdown("### 4. NFT Collection Stats")
st.sidebar.markdown("📊 Fetch statistics of a specific NFT collection.")
st.sidebar.markdown("**Example:**")
st.sidebar.code("'Show me the stats for the [Collection Name] collection'")
st.sidebar.caption('You can ask it to query only specific properties of the collection as well.')


# Feature 5: Get popular collections
st.sidebar.markdown("### 5. Popular NFT Collections")
st.sidebar.markdown("🌟 Discover popular NFT collections for a specified time range.")
st.sidebar.markdown("**Example:**")
st.sidebar.code("'Show me the popular collections for the last 7 days'")
st.sidebar.caption('You can specify the number of top collections (1-50) and time range (1h, 1d, 7d, 30d) to fetch.')

st.sidebar.markdown("---")
st.sidebar.markdown("For more details, visit our [official website](https://vtopia.io).")

with tab1:
    query = st.text_input("Ask about NFTs in your wallet, details by mint address or name, collection stats, or discover popular collections:")

    if st.button('Submit'):
        with st.spinner('Fetching NFT details...'):
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
                    if "Error" in raw_result:
                        st.write(raw_result)
                        st.stop()
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

features = [
    # Existing Features
    {
        "title": "🔍 View Your NFTs",
        "description": "Simply input your Solana wallet address and see all the NFTs you own.",
        "stage": "Launched",
    },
    {
        "title": "🔖 Details by Mint Address",
        "description": "Want to know more about an NFT? Just provide its mint address. You can also ask specific questions or request particular details.",
        "stage": "Launched",
    },
    {
        "title": "📛 Details by NFT Name",
        "description": "Search for an NFT using its name. Ask specific questions or request only the details you're interested in.",
        "stage": "Launched",
    },
    {
        "title": "📊 Collection Stats",
        "description": "Get insights on any NFT collection. Ask about specific stats or pose a question about the collection.",
        "stage": "Launched",
    },
    {
        "title": "🌟 Popular Collections",
        "description": "Discover the trending NFT collections. Choose from time ranges of 1 hour, 1 day, 7 days, or 30 days, and select your desired number of top collections (from 1 to 50).",
        "stage": "Launched",
    },
    # Upcoming Features
    {
        "title": "📝 List NFT on Vtopia",
        "description": "List NFT by its name on Vtopia",
        "stage": "Development",
    },
    {
        "title": "🛍️ Buy NFT from Vtopia",
        "description": "You can buy NFT just by its name",
        "stage": "Development",
    },
    {
        "title": "🔥 Bulk Actions",
        "description": "Buy/List Multiple NFT from Vtopia in single prompt",
        "stage": "Development",
    },
    {
        "title": "💼 Make collection offer",
        "description": "You can make collection offers with global traits on Vtopia by collection name",
        "stage": "Development",
    },
    {
        "title": "🤝 Make/Accept Offer",
        "description": "Make or accept offers for NFTs on Vtopia",
        "stage": "Development",
    }
]

STAGE_COLORS = {
    "Launched": "rgba(76, 175, 80, 0.5)",  # Greenish
    "Development": "rgba(255, 193, 7, 0.5)"  # Yellowish
}


def _get_stage_tag(stage):
    color = STAGE_COLORS.get(stage, "rgba(206, 205, 202, 0.5)")
    return (
        f'<span style="background-color: {color}; padding: 1px 6px; '
        "margin: 0 5px; display: inline; vertical-align: middle; "
        f"border-radius: 0.25rem; font-size: 0.75rem; font-weight: 400; "
        f'white-space: nowrap">{stage}'
        "</span>"
    )


with tab2:
    # Launched Features
    st.markdown("## 🚀 September 2023")
    st.markdown("<br>", unsafe_allow_html=True)  # Adding blank space
    for feature in features:
        if feature["stage"] == "Launched":
            stage_tag = _get_stage_tag(feature["stage"])
            st.markdown(f"#### {feature['title']} {stage_tag}", unsafe_allow_html=True)
            st.markdown(f"<div style='padding-left: 38px; margin-bottom: 15px;'><span style='color: gray;'>{feature['description']}</span></div>", unsafe_allow_html=True)

    st.markdown("---", unsafe_allow_html=True)

    # Development Features
    st.markdown("## 🛠️ October 2023")
    st.markdown("<br>", unsafe_allow_html=True)  # Adding blank space
    for feature in features:
        if feature["stage"] != "Launched":
            stage_tag = _get_stage_tag(feature["stage"])
            st.markdown(f"#### {feature['title']} {stage_tag}", unsafe_allow_html=True)
            st.markdown(f"<div style='padding-left: 38px; margin-bottom: 15px;'><span style='color: gray;'>{feature['description']}</span></div>", unsafe_allow_html=True)
