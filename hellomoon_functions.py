import requests

token = "d2445c17-080e-4438-894a-5151620ef396"
# collection_name = "the heist"


def get_hello_moon_collection_id(collection_name: str) -> tuple:
    url = "https://rest-api.hellomoon.io/v0/nft/collection/name"

    payload = {
        "searchStrategy": "levenshtein",
        "collectionName": collection_name
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {token}"
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    if not data["data"]:
        raise ValueError(f"Collection name {collection_name} not found.")

    retrieved_collection_name = data["data"][0]["collectionName"].strip()
    hello_moon_id = data["data"][0]["helloMoonCollectionId"]

    return hello_moon_id, retrieved_collection_name


def get_mint_addresses(hello_moon_id: str) -> list:
    url = "https://rest-api.hellomoon.io/v0/nft/collection/mints"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {token}"
    }

    mint_addresses = []
    page = 1

    while True:
        print(f"Fetching page {page}...")
        payload = {
            "helloMoonCollectionId": hello_moon_id,
            "limit": 100,
            "page": page
        }

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json().get("data", [])

        if not data:
            break

        mint_addresses.extend([item["nftMint"] for item in data])
        page += 1

    print(f"Found {len(mint_addresses)} mint addresses.")
    return mint_addresses


# collectionId = get_hello_moon_collection_id(collection_name)
# print(collectionId)
# mint_addresses = get_mint_addresses(collectionId)
# print(mint_addresses)
# print("THESE MANY MINT ADDRESSES: ", len(mint_addresses))
