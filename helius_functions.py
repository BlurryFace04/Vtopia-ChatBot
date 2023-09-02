import requests
import json

api_key = "26e5d0c4-0775-48dd-b45d-a86334e8f1b3"


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


# mint_addresses_example = ["5A3zYy7sioUXwTebzM56WrM9vd8H1cj3iYjq8rT1zkKQ",
#                           "FRBCnyJsPezKwJaZZwZhwLiAM5un1eUAwFNanRvy6MFd"]
# nft_data = fetch_nft_data(mint_addresses_example)
#
# save_to_json(nft_data)
