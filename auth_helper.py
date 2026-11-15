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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.join(script_dir, 'credentials.json')
    
    if not os.path.exists(credentials_path):
        print("Error: credentials.json not found in the current directory!")
        print("Please follow the instructions to create and download it from the Google Cloud Console.")
        return

    print("Initializing Google OAuth 2.0 Flow...")
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    
    # Run local server for authorization with offline access; fallback to ephemeral port if 8080 is occupied
    try:
        creds = flow.run_local_server(port=8080, prompt='consent', access_type='offline')
    except OSError:
        print("Port 8080 is occupied, binding to an available dynamic port...")
        creds = flow.run_local_server(port=0, prompt='consent', access_type='offline')
    
    # Load client secrets to inspect config
    with open(credentials_path, 'r') as f:
        client_secrets = json.load(f)
        
    web_config = client_secrets.get('web') or client_secrets.get('installed')
    client_id = web_config.get('client_id')
    client_secret = web_config.get('client_secret')
    refresh_token = creds.refresh_token

    masked_secret = f"{client_secret[:4]}...{client_secret[-4:]}" if client_secret and len(client_secret) > 8 else "***"
    masked_token = f"{refresh_token[:6]}...{refresh_token[-4:]}" if refresh_token and len(refresh_token) > 10 else "***"

    print("\n" + "="*60)
    print("SUCCESSFULLY AUTHENTICATED!")
    print("="*60)
    print(f"\nGOOGLE_CLIENT_ID: {client_id}")
    print(f"GOOGLE_CLIENT_SECRET: {masked_secret} (Stored securely in .env)")
    print(f"GOOGLE_REFRESH_TOKEN: {masked_token} (Stored securely in .env)")
    print("\n" + "="*60)

    # Auto-update .env file
    env_file = os.path.join(script_dir, ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        updated_lines = []
        updated_keys = set()
        for line in lines:
            if line.startswith("GOOGLE_CLIENT_ID="):
                updated_lines.append(f"GOOGLE_CLIENT_ID={client_id}\n")
                updated_keys.add("GOOGLE_CLIENT_ID")
            elif line.startswith("GOOGLE_CLIENT_SECRET="):
                updated_lines.append(f"GOOGLE_CLIENT_SECRET={client_secret}\n")
                updated_keys.add("GOOGLE_CLIENT_SECRET")
            elif line.startswith("GOOGLE_REFRESH_TOKEN="):
                updated_lines.append(f"GOOGLE_REFRESH_TOKEN={refresh_token}\n")
                updated_keys.add("GOOGLE_REFRESH_TOKEN")
            else:
                updated_lines.append(line)

        if "GOOGLE_REFRESH_TOKEN" not in updated_keys:
            updated_lines.append(f"GOOGLE_REFRESH_TOKEN={refresh_token}\n")

        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(updated_lines)

        print("\n✅ Successfully auto-updated .env with the new GOOGLE_REFRESH_TOKEN!")
    else:
        print("\n⚠️ .env file not found. Please create one with the values above.")

if __name__ == '__main__':
    main()

