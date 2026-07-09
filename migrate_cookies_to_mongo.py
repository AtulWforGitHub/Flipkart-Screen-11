"""
Migrate existing client_cookies.json to MongoDB
Run this once to save Rahul's cookies permanently to MongoDB
"""

import json
import os
from pymongo import MongoClient
from datetime import datetime, timezone
import certifi

# Load credentials
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://jagsir:1gmehyK0yuElYf4N@cluster0.rt55a2o.mongodb.net/?appName=Cluster0")

# Connect to MongoDB
mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo["flipkart"]
col_accounts = db["flipkart_accounts"]

# Read cookies from file
with open("client_cookies.json", "r") as f:
    cookies = json.load(f)

print(f"Loaded {len(cookies)} cookies from client_cookies.json")

# Check if Rahul account already exists
existing = col_accounts.find_one({"name": "Rahul"})

if existing:
    print(f"Account 'Rahul' already exists in MongoDB (account_id: {existing['account_id']})")
    print("Updating cookies...")
    col_accounts.update_one(
        {"name": "Rahul"},
        {"$set": {
            "cookies": cookies,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    print("✅ Cookies updated successfully!")
else:
    print("Creating new account 'Rahul' in MongoDB...")
    
    # Deactivate all other accounts first
    col_accounts.update_many({}, {"$set": {"active": False}})
    
    # Create new account
    account_doc = {
        "account_id": "rahul001",
        "name": "Rahul",
        "phone": "Unknown",
        "cookies": cookies,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "migrated_from_file"
    }
    
    col_accounts.insert_one(account_doc)
    print("✅ Account created successfully!")

print("\n" + "="*60)
print("Migration complete!")
print("Cookies are now permanently stored in MongoDB")
print("="*60)
