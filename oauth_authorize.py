"""
One-time authorization script.

Run this once per Gmail account you want the app to send from. It opens a
browser for that account to log in and click "Allow", then prints a TOML
snippet to paste into .streamlit/secrets.toml (or accounts.local.json for
local testing).

Usage:
    python oauth_authorize.py path/to/credentials.json you@gmail.com
"""

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main():
    if len(sys.argv) != 3:
        print("Usage: python oauth_authorize.py path/to/credentials.json you@gmail.com")
        sys.exit(1)

    credentials_path = sys.argv[1]
    email = sys.argv[2]
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(credentials_path) as f:
        client_config = json.load(f)["installed"]

    print("\nAuthorized:", email)
    print("\nAdd this to .streamlit/secrets.toml (or accounts.local.json for local dev):\n")
    print("[[gmail_accounts]]")
    print(f'email = "{email}"')
    print(f'client_id = "{client_config["client_id"]}"')
    print(f'client_secret = "{client_config["client_secret"]}"')
    print(f'refresh_token = "{creds.refresh_token}"')


if __name__ == "__main__":
    main()
