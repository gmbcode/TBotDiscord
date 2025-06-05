import json
import os
from bson.json_util import dumps
import secrets
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, redirect, jsonify, session
import requests
from dotenv import dotenv_values
config = dotenv_values(".env")

app = Flask(__name__)
app.secret_key = 'c67e60f3d01dedf374bb692f7b52070c'

# Google OAuth configuration
GOOGLE_CLIENT_ID = config['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = config['GOOGLE_CLIENT_SECRET']
GOOGLE_REDIRECT_URI = "http://localhost:8080/oauth/callback"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Scopes for accessing user email
SCOPES = ["openid", "email", "profile","https://www.googleapis.com/auth/tasks"]

# File to store OAuth data
OAUTH_DATA_FILE = "udb.json"
from Mongo_Access import DB_Client
db = DB_Client()
auth = db.clt['TBot_DB']['auth']
def load_oauth_data(user_id):
    """Load existing OAuth data from JSON file"""
    usr = auth.find_one({"user.user_id" : user_id})
    if usr is not None:
        del usr['_id']
    return usr


def save_oauth_data(user_id,data):
    """Save OAuth data to JSON file"""
    try:
        keys = list(data.keys())
        uid = str(keys[0])
        result = auth.update_one(
            {"user.user_id" : user_id},  # Filter: documents that have uid field
            {"$set": data},
            upsert=True
        )
    except Exception as ex:
        print(str(ex))



def generate_auth_url(user_id):
    """Generate Google OAuth authorization URL with state parameter"""
    state = json.dumps({"user_id": user_id, "nonce": secrets.token_urlsafe(16)})

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "response_type": "code",
        "access_type": "offline", # To get refresh token
        "include_granted_scopes": "true",
        "prompt": "consent",  # Force consent to ensure refresh token
        "state": state
    }

    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


@app.route('/')
def index():
    """Home page with login options"""
    return '''
    <h1>Google OAuth Server</h1>
    <p>Test the OAuth flow by clicking the link below:</p>
    <a href="/login?user_id=456">Login with Google (User ID: 456)</a><br><br>
    <a href="/data">View stored OAuth data</a>
    '''


@app.route('/login')
def login():
    """Initiate OAuth flow"""
    user_id = request.args.get('user_id')
    if not user_id:
        return "Error: user_id parameter is required", 400

    auth_url = generate_auth_url(user_id)
    return redirect(auth_url)


@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback from Google"""
    #TODO : Remove debug data from final production build
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        return f"OAuth Error: {error}", 400

    if not code or not state:
        return "Error: Missing code or state parameter", 400

    try:
        # Get user id from state
        state_data = json.loads(state)
        user_id = state_data.get('user_id')

        if not user_id:
            return "Error: Invalid state parameter", 400

        # Exchange authorization code for tokens
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT_URI
        }

        token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        token_response.raise_for_status()
        tokens = token_response.json()

        # Get user info using access token
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        user_response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
        user_response.raise_for_status()
        user_info = user_response.json()

        # Calculate expiration time
        expires_in = tokens.get('expires_in', 3600)  # Default to 1 hour
        expires_at = datetime.now() + timedelta(seconds=expires_in)

        # OAuth Data to store
        oauth_data = {
            "user" : {
                "email": user_info.get('email'),
                "access_token": tokens.get('access_token'),
                "refresh_token": tokens.get('refresh_token'),
                "expires_in": expires_in,
                "expires_at": expires_at.isoformat(),
                "state": state,
                "user_id": str(user_id),
                "created_at": datetime.now().isoformat(), # System timezone
                "timezone": "not_set", # User Timezone
                "user_info": user_info  # Store additional user info
            }
        }

        # Save to JSON file
        save_oauth_data(str(user_id),oauth_data)

        return f'''
        <h1>OAuth Success!</h1>
        <p><strong>User ID:</strong> {user_id}</p>
        <p><strong>Email:</strong> {user_info.get('email')}</p>
        <p><strong>Name:</strong> {user_info.get('name', 'N/A')}</p>
        <p><strong>Access Token:</strong> {tokens.get('access_token')[:20]}...</p>
        <p><strong>Refresh Token:</strong> {"Present" if tokens.get('refresh_token') else "Not received"}</p>
        <p><strong>Expires In:</strong> {expires_in} seconds</p>
        <p><strong>Expires At:</strong> {expires_at}</p>
        <br>
        <a href="/data">View all stored data</a> | <a href="/">Home</a>
        '''

    except json.JSONDecodeError:
        return "Error: Invalid state parameter format", 400
    except requests.RequestException as e:
        return f"Error communicating with Google: {str(e)}", 500
    except Exception as e:
        return f"Unexpected error: {str(e)}", 500


@app.route('/data')
def view_data():
    """View stored OAuth data (To be removed on prod build)"""
    # TODO : Remove from prod build or add some admin access code

    d = auth.find({})
    data = {}
    for document in d:
        del document['_id']
        data.update(document)


    if not data:
        return "<h1>No OAuth data stored yet</h1><br><a href='/'>Home</a>"

    html = "<h1>Stored OAuth Data</h1>"
    for user_id, user_data in data.items():
        html += f"""
        <div style='border: 1px solid #ccc; margin: 10px; padding: 10px;'>
            <h3>User ID: {user_id}</h3>
            <p><strong>Email:</strong> {user_data.get('email', 'N/A')}</p>
            <p><strong>Access Token:</strong> {user_data.get('access_token', 'N/A')[:30]}...</p>
            <p><strong>Refresh Token:</strong> {"Present" if user_data.get('refresh_token') else "Not available"}</p>
            <p><strong>Expires In:</strong> {user_data.get('expires_in', 'N/A')} seconds</p>
            <p><strong>Expires At:</strong> {user_data.get('expires_at', 'N/A')}</p>
            <p><strong>Created At:</strong> {user_data.get('created_at', 'N/A')}</p>
        </div>
        """

    html += "<br><a href='/'>Home</a>"
    return html


@app.route('/api/user/<user_id>')
def get_user_data(user_id):
    """API endpoint to get specific user's OAuth data"""
    # TODO : Remove from prod build or add some admin access code
    user_data = load_oauth_data(user_id)

    if not user_data:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user_data)


@app.route('/refresh/<user_id>')
def refresh_token(user_id):
    """Refresh access token for a specific user"""
    # TODO : Remove from prod build or add some admin access code
    data = load_oauth_data(user_id)
    user_data = data.get(user_id)

    if not user_data or not user_data.get('refresh_token'):
        return "Error: No refresh token available for this user", 400

    try:
        refresh_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": user_data['refresh_token'],
            "grant_type": "refresh_token"
        }

        response = requests.post(GOOGLE_TOKEN_URL, data=refresh_data)
        response.raise_for_status()
        new_tokens = response.json()

        # Update stored data
        expires_in = new_tokens.get('expires_in', 3600)
        expires_at = datetime.now() + timedelta(seconds=expires_in)

        user_data.update({
            "access_token": new_tokens.get('access_token'),
            "expires_in": expires_in,
            "expires_at": expires_at.isoformat(),
            "refreshed_at": datetime.now().isoformat()
        })

        # If new refresh token is provided, update it
        if 'refresh_token' in new_tokens:
            user_data['refresh_token'] = new_tokens['refresh_token']

        save_oauth_data(str(user_id),{"user": user_data})

        return f"Token refreshed successfully for user {user_id}. New expiration: {expires_at}"

    except requests.RequestException as e:
        return f"Error refreshing token: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0',port= 8080)