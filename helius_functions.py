import requests
import streamlit as st

api_key = st.secrets.helius_api_key
URL = f"https://rpc.helius.xyz/?api-key={api_key}"


def fetch_nft_data(mint_addresses: list) -> list:
    if not isinstance(mint_addresses, list):
        mint_addresses = [mint_addresses]

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

    response = requests.post(URL, headers={"Content-Type": "application/json"}, json=batch)
    response.raise_for_status()

    return response.json()


def extract_nft_data(nft: dict) -> dict:
    data = {"mint_address": nft.get("id")}

    content = nft.get("content", {})
    metadata = content.get("metadata", {})

    data["name"] = metadata.get("name")
    data["symbol"] = metadata.get("symbol")
    data["description"] = metadata.get("description")

    links = content.get("links", {})
    data["image"] = links.get("image")

    return data


def get_nfts_by_owner(address: str) -> list:
    page_number = 1
    limit = 1000
    all_nfts = []

    while True:
        payload = {
            "jsonrpc": "2.0",
            "id": "my-id",
            "method": "getAssetsByOwner",
            "params": {
                "ownerAddress": address,
                "page": page_number,
                "limit": limit,
            },
        }

        response = requests.post(URL, headers={"Content-Type": "application/json"}, json=payload)
        response_data = response.json()

        if "result" in response_data and "items" in response_data["result"]:
            nfts = response_data["result"]["items"]
            processed_nfts = [extract_nft_data(nft) for nft in nfts]
            all_nfts.extend(processed_nfts)

            if len(nfts) < limit:
                break

            page_number += 1
        else:
            break

    return all_nfts
