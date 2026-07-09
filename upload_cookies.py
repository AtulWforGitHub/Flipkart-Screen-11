"""
Script to upload Rahul's cookies to MongoDB manually.
This will create/update the account in flipkart_accounts collection.
"""

import json
import certifi
from pymongo import MongoClient
from datetime import datetime
import os

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://jagsir:1gmehyK0yuElYf4N@cluster0.rt55a2o.mongodb.net/?appName=Cluster0")
mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo["flipkart"]
col_accounts = db["flipkart_accounts"]

# Load Rahul's cookies
with open("client_cookies_RAHUL_PERMANENT.json", "r") as f:
    cookies = json.load(f)

print(f"Loaded {len(cookies)} cookies from file")

# Create account document
account_id = "RAHUL_PERMANENT"
account_doc = {
    "account_id": account_id,
    "name": "Rahul",  # Will be updated when cookies are actually used
    "phone": None,
    "cookies": cookies,
    "active": True,
    "created_at": datetime.utcnow().isoformat()
}

# Deactivate all other accounts
col_accounts.update_many({}, {"$set": {"active": False}})
print("Deactivated all existing accounts")

# Insert or update this account
result = col_accounts.update_one(
    {"account_id": account_id},
    {"$set": account_doc},
    upsert=True
)

if result.upserted_id:
    print(f"✓ Created new account: {account_id}")
else:
    print(f"✓ Updated existing account: {account_id}")

print(f"✓ Account is now active with {len(cookies)} cookies")
print("\nRestart the app to use these cookies!")
