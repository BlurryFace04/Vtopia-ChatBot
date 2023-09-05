import requests
import json
import streamlit as st


def get_popular_collections(time_range="1d", top=10):
    if time_range.endswith('d'):
        num_days = int(time_range[:-1])
        if num_days <= 1:
            time_range = "1d"
        elif num_days <= 7:
            time_range = "7d"
        else:
            time_range = "30d"
    if time_range.endswith('h'):
        time_range = "1h"

    st.write({"time_range": time_range, "top": top})

    url = "https://api-mainnet.magiceden.dev/v2/marketplace/popular_collections"
    headers = {"accept": "application/json"}
    params = {"timeRange": time_range}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = json.loads(response.text)

        for collection in data:
            collection.pop('description', None)

            collection['floorPrice'] = collection['floorPrice'] / 1_000_000_000

        limited_data = data[:top]
        return limited_data
    else:
        response.raise_for_status()
