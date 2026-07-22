import os
import requests

NOTION_KEY = os.getenv("NOTION_API_KEY")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")

url = f"https://api.notion.com/v1/databases/{NOTION_DB_ID}"
headers = {
    "Authorization": f"Bearer {NOTION_KEY}",
    "Notion-Version": "2022-06-28"
}

response = requests.get(url, headers=headers)
data = response.json()

print("\n" + "="*60)
print("📋 YOUR NOTION DATABASE COLUMNS")
print("="*60)

for name, prop in data.get("properties", {}).items():
    print(f"  • {name:25} → Type: {prop['type']}")

print("="*60)
print("\n✅ Copy these EXACT names into agents.py")
