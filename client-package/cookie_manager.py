"""
Cookie management utilities for MongoDB storage
"""
import json
from datetime import datetime
from pymongo import MongoClient
import certifi

# MongoDB connection (scoped client-access user: readWriteAnyDatabase)
MONGO_URI = "mongodb+srv://jagsir:JWff45t518S1d8F0@cluster0.rt55a2o.mongodb.net/?appName=Cluster0"
_mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
_db = _mongo["flipkart"]
_col_cookies = _db["cookies"]  # {account_name, cookies, updated_at}


def save_cookies_to_mongo(cookies: list, account_name: str = "default") -> bool:
    """
    Save cookies to MongoDB
    
    Args:
        cookies: List of cookie dicts
        account_name: Name/identifier for this cookie set
    
    Returns:
        True if saved successfully
    """
    try:
        doc = {
            "account_name": account_name,
            "cookies": cookies,
            "updated_at": datetime.utcnow(),
            "cookie_count": len(cookies)
        }
        
        # Upsert (update if exists, insert if not)
        _col_cookies.update_one(
            {"account_name": account_name},
            {"$set": doc},
            upsert=True
        )
        
        print(f"[+] Saved {len(cookies)} cookies to MongoDB as '{account_name}'")
        return True
    except Exception as e:
        print(f"[!] Failed to save cookies to MongoDB: {e}")
        return False


def load_cookies_from_mongo(account_name: str = "default") -> list:
    """
    Load cookies from MongoDB
    
    Args:
        account_name: Name/identifier for cookie set
    
    Returns:
        List of cookie dicts, or empty list if not found
    """
    try:
        doc = _col_cookies.find_one({"account_name": account_name})
        
        if doc and "cookies" in doc:
            cookies = doc["cookies"]
            updated_at = doc.get("updated_at", "unknown")
            print(f"[+] Loaded {len(cookies)} cookies from MongoDB ({account_name}, updated: {updated_at})")
            return cookies
        else:
            print(f"⚠ No cookies found in MongoDB for '{account_name}'")
            return []
    except Exception as e:
        print(f"[!] Failed to load cookies from MongoDB: {e}")
        return []


def list_cookie_accounts() -> list:
    """
    List all cookie accounts stored in MongoDB
    
    Returns:
        List of dicts with account info
    """
    try:
        accounts = []
        for doc in _col_cookies.find({}, {"account_name": 1, "cookie_count": 1, "updated_at": 1}):
            accounts.append({
                "account_name": doc.get("account_name"),
                "cookie_count": doc.get("cookie_count", 0),
                "updated_at": doc.get("updated_at")
            })
        return accounts
    except Exception as e:
        print(f"[!] Failed to list cookie accounts: {e}")
        return []


if __name__ == "__main__":
    # Test: List existing cookie accounts
    print("\n" + "="*60)
    print("Cookie Accounts in MongoDB")
    print("="*60)
    for acc in list_cookie_accounts():
        print(f"  - {acc['account_name']}: {acc['cookie_count']} cookies (updated: {acc['updated_at']})")
