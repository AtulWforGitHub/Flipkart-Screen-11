"""Check what accounts are in MongoDB"""
import certifi
from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://jagsir:1gmehyK0yuElYf4N@cluster0.rt55a2o.mongodb.net/?appName=Cluster0")
mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = mongo["flipkart"]
col_accounts = db["flipkart_accounts"]

accounts = list(col_accounts.find({}, {"_id": 0, "account_id": 1, "name": 1, "active": 1, "cookies": 1}))

print(f"Found {len(accounts)} accounts in MongoDB:\n")
for acc in accounts:
    cookie_count = len(acc.get("cookies", []))
    active = "✓ ACTIVE" if acc.get("active") else "  inactive"
    print(f"{active} | {acc['account_id']:<20} | {acc['name']:<15} | {cookie_count} cookies")
