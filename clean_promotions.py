"""
Gmail Inbox Cleaner Utility.
Moves bulk promotional, social, or update emails to Trash.
"""
import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_emails import get_gmail_service


def clean_category(service, creds, query, max_to_clean=1000):
    print(f"\nSearching for emails matching: '{query}'...")
    access_token = creds.token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify"
    
    total_cleaned = 0
    batch_count = 1
    
    while total_cleaned < max_to_clean:
        fetch_limit = min(500, max_to_clean - total_cleaned)
        results = service.users().messages().list(
            userId='me', q=query, maxResults=fetch_limit
        ).execute()
        
        messages = results.get('messages', [])
        if not messages:
            print(f"No more emails found in '{query}'.")
            break
            
        msg_ids = [m['id'] for m in messages]
        print(f"Trashing batch {batch_count} of '{query}' ({len(msg_ids)} emails)...")
        
        payload = {
            "ids": msg_ids,
            "addLabelIds": ["TRASH"],
            "removeLabelIds": ["INBOX"]
        }
        
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code in [200, 204]:
            total_cleaned += len(msg_ids)
            print(f"Successfully trashed batch {batch_count}. Total cleaned so far: {total_cleaned}")
        else:
            print(f"Failed to trash batch: {r.status_code} - {r.text}")
            break
            
        batch_count += 1
        time.sleep(1)  # Respect API quotas
        
    print(f"Completed '{query}'! Total Cleaned: {total_cleaned}")
    return total_cleaned


def main():
    service = get_gmail_service()
    
    # Check arguments
    if "--all" in sys.argv:
        categories = ["category:promotions", "category:updates", "category:social"]
    elif "--social" in sys.argv:
        categories = ["category:social"]
    elif "--updates" in sys.argv:
        categories = ["category:updates"]
    else:
        categories = ["category:promotions"]

    creds = service._http.credentials
    total = 0
    for cat in categories:
        total += clean_category(service, creds, cat)

    print(f"\n🎉 Clean-up complete! Total emails moved to Trash: {total}")


if __name__ == '__main__':
    main()
