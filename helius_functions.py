import requests
import json
import streamlit as st

api_key = st.secrets.helius_api_key


def fetch_nft_data(mint_addresses: list) -> list:
    if not isinstance(mint_addresses, list):
        mint_addresses = [mint_addresses]

    url = f"https://rpc.helius.xyz/?api-key={api_key}"

    batch = [
        {
            "jsonrpc": "2.0",
            "id": f"my-id-{i}",
            "method": "getAsset",
            "params": {
                "id": mint_address
            }
        }
        for i, mint_address in enumerate(mint_addresses)
    ]

    response = requests.post(url, headers={"Content-Type": "application/json"}, json=batch)
    response.raise_for_status()

    return response.json()


def save_to_json(data, filename="nft_data2.json"):
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)
