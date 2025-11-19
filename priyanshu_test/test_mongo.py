
# mongo_insert_demo.py

import os
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError

# 1. Load variables from .env
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "occhub_summary")
COLLECTION_NAME = os.getenv("COLLECTION_SUMMARY", "summary")

if not MONGODB_URL:
    raise RuntimeError("MONGODB_URL is not set in .env")


def get_collection():
    """
    Create a MongoDB client and return the 'summary' collection.
    tlsAllowInvalidCertificates=True is required on some office networks
    where SSL is intercepted by a proxy.
    """
    client = MongoClient(
        MONGODB_URL,
        tlsAllowInvalidCertificates=True,  # <- bypass strict SSL validation
    )
    db = client[DATABASE_NAME]
    return db[COLLECTION_NAME]


def insert_summary(sid: str, uid: str, summary_text: str):
    """Insert one summary document and return the inserted _id."""
    collection = get_collection()

    doc = {
        "sid": sid,                # Summary id
        "uid": uid,                # User id
        "summary": summary_text,   # Summary text
        "created_at": datetime.utcnow(),
    }

    result = collection.insert_one(doc)
    return result.inserted_id, collection


if __name__ == "__main__":
    try:
        # Example dummy data – change as you like
        sid = "DEC-1-3"
        uid = "user-789"
        summary_text = "Scattered clouds with light winds near HYD."

        inserted_id, collection = insert_summary(sid, uid, summary_text)
        print("✅ Inserted document with _id:", inserted_id)

        total = collection.count_documents({})
        print("📦 Total documents in 'summary' collection:", total)

    except ConnectionFailure as e:
        print("❌ Connection failed:", e)
    except PyMongoError as e:
        print("❌ Mongo error:", e)
    except Exception as e:
        print("❌ Unexpected error:", e)

