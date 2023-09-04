import requests
from collections import OrderedDict
import streamlit as st

token = st.secrets.hellomoon_api_key


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


def fetch_collection_stats(collectionId):
    url = "https://rest-api.hellomoon.io/v0/nft/collection/leaderboard/stats"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {token}"
    }

    payload = {
        "helloMoonCollectionId": collectionId,
        "granularity": ["THIRTY_MIN", "ONE_HOUR", "SIX_HOUR", "HALF_DAY", "ONE_DAY", "ONE_WEEK", "ONE_MONTH"]
    }

    response = requests.post(url, json=payload, headers=headers)
    response_data = response.json()

    # Renaming fields directly after fetching
    for item in response_data["data"]:
        if 'narrative' in item:
            item['description'] = item.pop('narrative')
        if 'sample_image' in item:
            item['image'] = item.pop('sample_image')
        if 'external_url' in item:
            item['website'] = item.pop('external_url')

    result = OrderedDict()

    order_of_fields = [
        "collectionName", "helloMoonCollectionId", "description", "image", "website", "slug", "mint_price_mode",
        "listing_count", "supply", "floorPrice", "current_owner_count", "market_cap_usd", "market_cap_sol",
        "avg_price_sol", "avg_price_usd", "owners_avg_usdc_holdings", "magic_eden_holding",
        "magic_eden_holding_proportion",
        "average_wash_score"
    ]

    convert_fields = ["volume", "price_delta", "volume_delta", "floorPrice"]

    granularity_map = {
        "THIRTY_MIN": "thirty_min",
        "ONE_HOUR": "one_hour",
        "SIX_HOUR": "six_hour",
        "HALF_DAY": "half_day",
        "ONE_DAY": "one_day",
        "ONE_WEEK": "one_week",
        "ONE_MONTH": "one_month"
    }

    granularity_field_mapping = {
        "THIRTY_MIN": {
            "avg_price_now_30_minutes": "avg_price_now",
            "smart_inflow_30_minutes": "smart_inflow",
            "smart_money_netflow_score_30_minutes": "smart_money_netflow_score",
            "cnt_buyers_30min": "cnt_buyers",
            "cnt_sellers_30min": "cnt_sellers"
        },
        "ONE_HOUR": {
            "avg_price_now_1_hour": "avg_price_now",
            "smart_inflow_1_hour": "smart_inflow",
            "smart_money_netflow_score_1_hour": "smart_money_netflow_score",
            "cnt_buyers_1h": "cnt_buyers",
            "cnt_sellers_1h": "cnt_sellers"
        },
        "SIX_HOUR": {
            "avg_price_now_6_hour": "avg_price_now",
            "smart_inflow_6_hour": "smart_inflow",
            "smart_money_netflow_score_6_hour": "smart_money_netflow_score",
            "cnt_buyers_6h": "cnt_buyers",
            "cnt_sellers_6h": "cnt_sellers"
        },
        "HALF_DAY": {
            "avg_price_now_12_hour": "avg_price_now",
            "smart_inflow_12_hour": "smart_inflow",
            "smart_money_netflow_score_12_hour": "smart_money_netflow_score",
            "cnt_buyers_12h": "cnt_buyers",
            "cnt_sellers_12h": "cnt_sellers"
        },
        "ONE_DAY": {
            "smart_money_netflow_score_1d": "smart_money_netflow_score",
            "cnt_buyers_1d": "cnt_buyers",
            "cnt_sellers_1d": "cnt_sellers"
        },
        "ONE_WEEK": {
            "avg_price_now_1_week": "avg_price_now",
            "smart_money_netflow_score_7d": "smart_money_netflow_score"
        },
        "ONE_MONTH": {
            "avg_price_now_1_month": "avg_price_now",
            "smart_inflow_1_month": "smart_inflow",
            "smart_money_netflow_score_1_month": "smart_money_netflow_score",
            "cnt_buyers_28d": "cnt_buyers",
            "cnt_sellers_28d": "cnt_sellers"
        }
    }

    main_fields_processed = False

    for item in response_data["data"]:
        granularity_key = granularity_map.get(item["granularity"])

        if not main_fields_processed:
            for key in order_of_fields:
                if key in item:
                    result[key] = item[key] / 1e9 if key in convert_fields else item[key]
            main_fields_processed = True

        granularity_data = {}
        for field in ["volume", "price_percent_change", "volume_percent_change"]:
            if field in item:
                granularity_data[field] = item[field] / 1e9 if field in convert_fields else item[field]
        for original, new in granularity_field_mapping[item["granularity"]].items():
            if original in item:
                granularity_data[new] = item[original]

        if 'cnt_buyers' in granularity_data:
            granularity_data['buyers'] = granularity_data.pop('cnt_buyers')
        if 'cnt_sellers' in granularity_data:
            granularity_data['sellers'] = granularity_data.pop('cnt_sellers')

        result[granularity_key] = granularity_data

    return result
