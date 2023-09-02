from pymongo import MongoClient, InsertOne
from typing import Optional, Dict
from datetime import datetime
import streamlit as st

client = MongoClient(st.secrets.MONGODB_URI)
db = client['Vtopia']
nft_metadata_collection = db['nft_metadata']
collection_info_collection = db['collection_info']
failed_chunks_collection = db['failed_chunks']


def insert_nft_metadata(metadata, collection):
    if isinstance(metadata, list):
        results = [{**doc['result'], 'collection': collection} for doc in metadata]

        chunks = [results[i:i + 7000] for i in range(0, len(results), 7000)]

        for chunk in chunks:
            insert_requests = [InsertOne(doc) for doc in chunk]
            nft_metadata_collection.bulk_write(insert_requests, ordered=False)

    else:
        result = {**metadata['result'], 'collection': collection}
        mint_address = result["id"]
        nft_metadata_collection.update_one(
            {"id": mint_address},
            {"$set": result},
            upsert=True
        )


def insert_collection_info(collection_name, collectionId):
    doc = {
        "collectionName": collection_name,
        "helloMoonCollectionId": collectionId
    }

    result = collection_info_collection.update_one(
        {"helloMoonCollectionId": collectionId},
        {"$set": doc},
        upsert=True
    )

    if result.upserted_id:
        return result.upserted_id
    else:
        found_doc = collection_info_collection.find_one({"helloMoonCollectionId": collectionId})
        return found_doc["_id"]


def insert_failed_chunks(chunk, chunk_number, helloMoonCollectionId, collectionName):
    data = {
        'timestamp': datetime.now(),
        'chunk_number': chunk_number,
        'chunk': chunk,
        'helloMoonCollectionId': helloMoonCollectionId,
        'collectionName': collectionName
    }

    failed_chunks_collection.insert_one(data)


def collection_info_exists(collectionId: str) -> bool:
    return bool(collection_info_collection.find_one({"helloMoonCollectionId": collectionId}))


def get_nft_metadata_from_mongodb(nft_name: str) -> Optional[Dict]:
    nft_document = nft_metadata_collection.find_one({"content.metadata.name": nft_name})

    if nft_document:
        return nft_document
    return None
