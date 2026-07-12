"""
Upload server cookies to MongoDB as 'server' account
"""
import json
from cookie_manager import save_cookies_to_mongo

# Load current cookies (these should match server cookies)
with open('client_cookies.json') as f:
    cookies = json.load(f)

print(f"\nUploading {len(cookies)} cookies to MongoDB as 'server' account...")

# Upload to MongoDB with 'server' account name
if save_cookies_to_mongo(cookies, "server"):
    print("[+] Server cookies uploaded to MongoDB")
    print("    Now the server can load from MongoDB!")
else:
    print("[!] Upload failed")
