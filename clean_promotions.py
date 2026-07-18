import os
import sys
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Load env variables manually from .env
env = {}
with open(".env", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip()

GOOGLE_CLIENT_ID = env.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = env.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = env.get("GOOGLE_REFRESH_TOKEN")

def get_credentials():
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    creds.refresh(Request())
    return creds

def main():
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)
    
    print("Searching for emails in category:promotions...")
    query = "category:promotions"
    
    msg_ids = []
    page_token = None
    max_to_clean = 1000  # Clean up to 1,000 of your promotional emails
    
    while len(msg_ids) < max_to_clean:
        results = service.users().messages().list(
            userId='me', q=query, pageToken=page_token, maxResults=500
        ).execute()
        
        messages = results.get('messages', [])
        if not messages:
            break
            
        msg_ids.extend([m['id'] for m in messages])
        page_token = results.get('nextPageToken')
        if not page_token:
            break
            
    msg_ids = msg_ids[:max_to_clean]
    
    if not msg_ids:
        print("No emails found in category:promotions.")
        return
        
    print(f"Found {len(msg_ids)} promotional email(s). Moving them to Trash...")
    
    # Use direct REST API call for batchModify to add TRASH label and remove INBOX label
    access_token = creds.token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify"
    
    batch_size = 500
    for i in range(0, len(msg_ids), batch_size):
        batch = msg_ids[i:i+batch_size]
        print(f"Trashing batch {i // batch_size + 1} ({len(batch)} emails)...")
        payload = {
            "ids": batch,
            "addLabelIds": ["TRASH"],
            "removeLabelIds": ["INBOX"]
        }
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code == 204 or r.status_code == 200:
            print(f"Successfully trashed batch {i // batch_size + 1}")
        else:
            print(f"Failed to trash batch: {r.status_code} - {r.text}")
        
    print("Successfully moved all promotional emails to Trash!")

if __name__ == '__main__':
    main()
