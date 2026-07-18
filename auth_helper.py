import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# We need gmail.modify to read emails, modify labels, and send replies.
# We also include calendar.readonly in case we implement calendar checks.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def main():
    credentials_path = 'credentials.json'
    
    if not os.path.exists(credentials_path):
        print("Error: credentials.json not found in the current directory!")
        print("Please follow the instructions to create and download it from the Google Cloud Console.")
        return

    print("Initializing Google OAuth 2.0 Flow...")
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    
    # Run the local server for authorization
    creds = flow.run_local_server(port=8080, prompt='consent')
    
    # Load client secrets to print ID and Secret directly
    with open(credentials_path, 'r') as f:
        client_secrets = json.load(f)
        
    web_config = client_secrets.get('web') or client_secrets.get('installed')
    client_id = web_config.get('client_id')
    client_secret = web_config.get('client_secret')

    print("\n" + "="*60)
    print("SUCCESSFULLY AUTHENTICATED!")
    print("="*60)
    print("\nCopy these values and store them securely in a safe place:")
    print(f"\nGOOGLE_CLIENT_ID:\n{client_id}")
    print(f"\nGOOGLE_CLIENT_SECRET:\n{client_secret}")
    print(f"\nGOOGLE_REFRESH_TOKEN:\n{creds.refresh_token}")
    print("\n" + "="*60)

if __name__ == '__main__':
    main()
