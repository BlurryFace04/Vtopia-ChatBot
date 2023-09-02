from moralis import sol_api
import requests
import streamlit as st

api_key = st.secrets.moralis_api_key

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
        "name": detailed_response.get("name"),
        "symbol": detailed_response.get("symbol"),
        "mint": initial_response.get("mint"),
        "description": detailed_response.get("description"),
        "image": detailed_response.get("image"),
        "external_url": detailed_response.get("external_url"),
        "edition": detailed_response.get("edition"),
        "standard": initial_response.get("standard"),
        "updateAuthority": initial_response.get("metaplex", {}).get("updateAuthority"),
        "sellerFeeBasisPoints": initial_response.get("metaplex", {}).get("sellerFeeBasisPoints"),
        "primarySaleHappened": initial_response.get("metaplex", {}).get("primarySaleHappened"),
        "owners": initial_response.get("metaplex", {}).get("owners"),
        "isMutable": initial_response.get("metaplex", {}).get("isMutable"),
        "masterEdition": initial_response.get("metaplex", {}).get("masterEdition"),
        "traits": traits,
        "properties": detailed_response.get("properties")
    }

    combined_data = {key: val for key, val in combined_data.items() if val is not None}

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
