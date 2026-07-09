"""
Check what accounts are in MongoDB flipkart_accounts collection.
"""

import certifi
from pymongo import MongoClient
import os

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://jagsir:1gmehyK0yuElYf4N@cluster0.rt55a2o.mongodb.net/?appName=Cluster0")
mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo["flipkart"]
col_accounts = db["flipkart_accounts"]

print("=" * 60)
print("FLIPKART ACCOUNTS IN MONGODB")
print("=" * 60)

accounts = list(col_accounts.find({}, {"_id": 0}))

if not accounts:
    print("No accounts found in database!")
else:
    for i, acc in enumerate(accounts, 1):
        print(f"\n[{i}] Account ID: {acc.get('account_id')}")
        print(f"    Name: {acc.get('name')}")
        print(f"    Phone: {acc.get('phone', 'N/A')}")
        print(f"    Active: {acc.get('active', False)}")
        print(f"    Cookies: {len(acc.get('cookies', []))} items")
        print(f"    Created: {acc.get('created_at', 'N/A')}")

print("\n" + "=" * 60)
print(f"Total accounts: {len(accounts)}")
