import base64
import hashlib
import secrets
import requests
import webbrowser
from urllib.parse import urlencode

# Constants (Replace with your actual values)
CLIENT_ID = '862789333054-srkm4fonl18ajddi6ct5n22622epfkve.apps.googleusercontent.com'

# OAuth local server settings
LOCAL_SERVER_PORT = 8080
LOCAL_SERVER_HOST = 'localhost'
REDIRECT_URI = f'http://{LOCAL_SERVER_HOST}:{LOCAL_SERVER_PORT}/'

def create_code_verifier():
    """Create a secure, random code_verifier."""
    token = secrets.token_urlsafe(64)
    return token[:128]

def create_code_challenge(code_verifier):
    """Transform the code_verifier into a code_challenge."""
    code_challenge = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode().replace('=', '')
    return code_challenge

def get_authorization_url(code_challenge):
    """Construct the authorization URL."""
    query_params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'https://www.googleapis.com/auth/drive.file',
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(query_params)}"
    return auth_url

def exchange_code_for_token(code_verifier, authorization_code):
    """Exchange the authorization code for an access token."""
    token_url = 'https://oauth2.googleapis.com/token'
    data = {
        'client_id': CLIENT_ID,
        'grant_type': 'authorization_code',
        'code': authorization_code,
        'redirect_uri': REDIRECT_URI,
        'code_verifier': code_verifier
    }
    response = requests.post(token_url, data=data)
    return response.json()  # This will contain the access token and refresh token

# Exported functions to be used by the addon
def initiate_oauth_flow():
    """Initiate OAuth flow."""
    code_verifier = create_code_verifier()
    code_challenge = create_code_challenge(code_verifier)
    auth_url = get_authorization_url(code_challenge)
    webbrowser.open(auth_url)
    return code_verifier

def handle_oauth_redirect(code_verifier, authorization_code):
    """Handle the OAuth redirect and exchange the code for a token."""
    token_data = exchange_code_for_token(code_verifier, authorization_code)
    return token_data
