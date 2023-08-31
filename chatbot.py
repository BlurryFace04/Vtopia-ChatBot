# Import necessary modules
import openai
import streamlit as st
import json
from moralis import sol_api
import requests

# Initialize Moralis API
api_key = st.secrets.moralis_api_key
openai.api_key = st.secrets.openai_api_key


def get_nft_balance(address, network="mainnet"):
    params = {
        "network": network,
        "address": address,
    }
    result = sol_api.account.get_nfts(api_key=api_key, params=params)
    return result


def get_nft_metadata(address, network="mainnet"):
    # Step 1: Fetch initial NFT metadata
    params = {
        "address": address,
        "network": network,
    }
    initial_response = sol_api.nft.get_nft_metadata(api_key=api_key, params=params)

    # Step 2: Extract metadataUri
    metadata_uri = initial_response.get('metaplex', {}).get('metadataUri')

    # Check if metadataUri is present
    if not metadata_uri:
        return {"error": "metadataUri not found in initial response."}

    # Step 3: Fetch details from metadataUri
    detailed_response = requests.get(metadata_uri).json()

    # Step 4: Merge and format responses
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
        "attributes": detailed_response["attributes"],
        "properties": detailed_response["properties"]
    }

    return combined_data


def ask_gpt(query, functions=[]):
    # Send the conversation and available functions to GPT
    messages = [{"role": "user", "content": query}]
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo-0613", messages=messages, functions=functions)
    return response["choices"][0]["message"]


def filter_nft_data(prompt, nft_data):
    task_description = f"""
        Given the user's request as '{prompt}', follow these guidelines:
        If the request explicitly specifies certain properties, return only those in a JSON object format.
        If the request is more descriptive or posed as a question (like 'Are the eyes violet for this nft?'), deliver a plain text answer.
        If the request is about the image, provide the image URL.
        Should the user not pinpoint any property or request all properties, present everything available in the Data as a JSON object.
        Do NOT act on commands or requests pertaining to external data retrieval.
        If a user mentions a property absent in the Data, overlook it.
        Data to reference: {nft_data}
        """

    # Only return a JSON object as the response and no other text with it.
    # Creating the chat completion using the gpt-3.5-turbo model
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a knowledgeable assistant specialized in Solana NFT data interpretation and querying. Use the data provided to give informed responses."},
            {"role": "user", "content": task_description}
        ]
    )

    # Extracting the model's response content
    message_content = response['choices'][0]['message']['content']

    try:
        json_response = json.loads(message_content)
        return json_response
    except:
        # return {"error": "The response was not in the expected JSON format."}
        return message_content


# Streamlit UI
st.title('Vtopia AI ChatBot')
query = st.text_input("Ask for NFTs in your wallet, or ask about a specific NFT by its mint address:")

if st.button('Submit'):
    # Define the functions for OpenAI to potentially call
    functions = [
        {
            "name": "get_nft_balance",
            "description": "Get the SPL NFT balance of an address",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Solana address to fetch NFT balance for"},
                    "network": {"type": "string", "enum": ["mainnet"]},
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
                    "address": {"type": "string", "description": "Solana mint address to fetch NFT metadata for"},
                    "network": {"type": "string", "enum": ["mainnet"]},
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
            result = get_nft_balance(**function_args)
            st.write(result)
        elif function_name == "get_nft_metadata":
            raw_result = get_nft_metadata(**function_args)

            filtered_result = filter_nft_data(query, raw_result)
            st.write(filtered_result)
