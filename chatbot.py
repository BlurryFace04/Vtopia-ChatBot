import openai
import streamlit as st
import json
from moralis import sol_api
import requests

api_key = st.secrets.moralis_api_key
openai.api_key = st.secrets.openai_api_key


def get_nft_balance(address):
    params = {
        "network": "mainnet",
        "address": address,
    }
    result = sol_api.account.get_nfts(api_key=api_key, params=params)
    return result


def get_nft_metadata(address):
    params = {
        "address": address,
        "network": "mainnet",
    }
    initial_response = sol_api.nft.get_nft_metadata(api_key=api_key, params=params)

    metadata_uri = initial_response.get('metaplex', {}).get('metadataUri')

    if not metadata_uri:
        raise ValueError("No metadataUri found in the initial response.")

    detailed_response = requests.get(metadata_uri).json()

    attributes_list = detailed_response.get("attributes", [])
    traits = {item["trait_type"]: item["value"] for item in attributes_list}

    combined_data = {
        "name": detailed_response["name"],
        "symbol": detailed_response["symbol"],
        "mint": initial_response["mint"],
        "description": detailed_response["description"],
        "image": detailed_response["image"],
        "external_url": detailed_response["external_url"],
        "edition": detailed_response.get("edition", None),
        "standard": initial_response["standard"],
        "updateAuthority": initial_response["metaplex"]["updateAuthority"],
        "sellerFeeBasisPoints": initial_response["metaplex"]["sellerFeeBasisPoints"],
        "primarySaleHappened": initial_response["metaplex"]["primarySaleHappened"],
        "owners": initial_response["metaplex"]["owners"],
        "isMutable": initial_response["metaplex"]["isMutable"],
        "masterEdition": initial_response["metaplex"]["masterEdition"],
        "traits": traits,  # Using the transformed traits here
        "properties": detailed_response["properties"]
    }

    return combined_data


def get_nft_image(address):
    params = {
        "address": address,
        "network": "mainnet",
    }
    initial_response = sol_api.nft.get_nft_metadata(api_key=api_key, params=params)

    metadata_uri = initial_response.get('metaplex', {}).get('metadataUri')

    if not metadata_uri:
        raise ValueError("No metadataUri found in the initial response.")

    metadata_response = requests.get(metadata_uri).json()

    image_url = metadata_response.get('image')

    if not image_url:
        raise ValueError("No image_url found in the metadata response.")

    return image_url


def display_nft_with_image(nft):
    cols = st.columns([2, 5])
    image_url = get_nft_image(nft['mint'])
    solscan_url = f"https://explorer.solana.com/address/{nft['mint']}"
    image_html = f"""
    <a href="{solscan_url}" target="_blank">
        <img src="{image_url}" style="border-radius: 8px; width: 200px;">
    </a>
    <br>
    <br>
    """
    cols[0].markdown(image_html, unsafe_allow_html=True)
    cols[0].write(f"<center><h6>{nft['name']}</h6></center>", unsafe_allow_html=True)
    nft_without_name = {key: val for key, val in nft.items() if key != 'name'}
    cols[1].write(nft_without_name)
    st.markdown("<br>", unsafe_allow_html=True)


def ask_gpt(query, functions=[]):
    messages = [{"role": "user", "content": query}]
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo-0613", messages=messages, functions=functions)
    return response["choices"][0]["message"]


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


st.title('Vtopia AI ChatBot')
query = st.text_input("Ask for NFTs in your wallet, or ask about a specific NFT by its mint address:")

if st.button('Submit'):
    functions = [
        {
            "name": "get_nft_balance",
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
            "name": "get_nft_metadata",
            "description": "Get metadata of a SPL NFT",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Solana mint address to fetch NFT metadata for"}
                },
                "required": ["address"],
            },
        }
    ]

    response_message = ask_gpt(query, functions)

    if response_message.get("function_call"):
        function_name = response_message["function_call"]["name"]
        function_args = json.loads(response_message["function_call"]["arguments"])

        if function_name == "get_nft_balance":
            nfts = get_nft_balance(**function_args)
            for nft in nfts:
                display_nft_with_image(nft)

        elif function_name == "get_nft_metadata":
            raw_result = get_nft_metadata(**function_args)
            solscan_url = f"https://explorer.solana.com/address/{raw_result['mint']}"
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


            filtered_result = filter_nft_data(query, raw_result)
            st.write(filtered_result)
