import bpy
from . import auth
from . import drive
import threading
import http
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser

bl_info = {
    "name": "DriveSnapshot",
    "author": "Quentin Steinke",
    "version": (0, 1),
    "blender": (4, 0, 0),
    "location": "Preferences > DriveSnapshot",
    "description": "A Blender addon to save and load snapshots to Google Drive.",
    "category": "System",
}

global httpd_server
httpd_server = None

# OAuth local server settings
LOCAL_SERVER_PORT = 8080
LOCAL_SERVER_HOST = 'localhost'
REDIRECT_URI = f'http://{LOCAL_SERVER_HOST}:{LOCAL_SERVER_PORT}/'

# Define the addon's preferences here
class GoogleDrivePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    # Add properties to store the login state and username
    is_logged_in: bpy.props.BoolProperty(default=False)
    logged_in_username: bpy.props.StringProperty(default="")

    # Temporary in-memory storage for the code verifier
    code_verifier: bpy.props.StringProperty(default="")

    # Access and Refresh tokens
    access_token: bpy.props.StringProperty(default="")
    refresh_token: bpy.props.StringProperty(default="")

    # UI for the addon preferences
    def draw(self, context):
        layout = self.layout
        prefs = bpy.context.preferences.addons[__name__].preferences

        # Display the login state and the button based on whether the user is logged in
        if prefs.is_logged_in:
            layout.label(text=f"Logged in as: {prefs.logged_in_username}")
            layout.operator("custom.logout", text="Logout")
        else:
            layout.operator("custom.oauth_login", text="Login with Google")



# Define a class that can handle stopping the server
class StoppableHTTPServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_running = True

    def serve_forever(self, poll_interval=0.5):
        while self._is_running:
            self.handle_request()

    def stop_server(self):
        self._is_running = False

# OAuth local server handler
class OAuthLocalServerHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if 'code' in self.path:
            # Parse the authorization code from the query string
            code = self.path.split('code=')[1].split('&')[0]
            bpy.ops.custom.oauth_token_exchange(authorization_code=code)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authentication successful. You can close this window.")
            threading.Thread(target=self.shutdown_server, args=(self.server,), daemon=True).start()
        else:
            self.send_error(400, "Bad Request: No code parameter in request")

    def shutdown_server(self, server):
        server.stop_server()

# Define your operators that interact with auth.py here
class OAuthLoginOperator(bpy.types.Operator):
    """Operator to start the OAuth login process."""
    bl_idname = "custom.oauth_login"
    bl_label = "Login with Google"

    def execute(self, context):
        prefs = bpy.context.preferences.addons[__name__].preferences
        prefs.code_verifier = auth.create_code_verifier()
        code_challenge = auth.create_code_challenge(prefs.code_verifier)
        auth_url = auth.get_authorization_url(code_challenge)
        webbrowser.open(auth_url)
        threading.Thread(target=self.run_local_server, daemon=True).start()
        return {'FINISHED'}

    def run_local_server(self):
        global httpd_server
        httpd_server = StoppableHTTPServer((LOCAL_SERVER_HOST, LOCAL_SERVER_PORT), OAuthLocalServerHandler)
        server_thread = threading.Thread(target=httpd_server.serve_forever, daemon=True)
        server_thread.start()

class LogoutOperator(bpy.types.Operator):
    """Operator to handle logout process."""
    bl_idname = "custom.logout"
    bl_label = "Logout"

    def execute(self, context):
        prefs = bpy.context.preferences.addons[__name__].preferences
        prefs.access_token = ""
        prefs.refresh_token = ""
        prefs.is_logged_in = False
        prefs.logged_in_username = ""
        self.report({'INFO'}, "Logged out successfully.")
        return {'FINISHED'}

class OAuthTokenExchangeOperator(bpy.types.Operator):
    """Operator to handle token exchange after receiving the authorization code."""
    bl_idname = "custom.oauth_token_exchange"
    bl_label = "Exchange Authorization Code for Token"
    authorization_code: bpy.props.StringProperty()

    def execute(self, context):
        prefs = bpy.context.preferences.addons[__name__].preferences
        try:
            # Exchange the authorization code for a token
            client_secret = "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"
            token_data = auth.exchange_code_for_token(prefs.code_verifier, self.authorization_code, client_secret)

            # Securely store the token data
            # Here you need to implement your encryption and secure storage solution.
            # For demonstration purposes, we're assigning the tokens directly.
            # WARNING: Tokens should be encrypted before storing in a production environment.
            prefs.access_token = token_data['access_token']
            prefs.refresh_token = token_data.get('refresh_token', '')

            # Clear the code verifier as it's no longer needed
            prefs.code_verifier = ""

            # Use the access token to get the user's profile information
            user_profile = drive.get_user_profile(prefs.access_token)
            print("User Profile:", user_profile)  # For debugging purposes
            if 'names' in user_profile and len(user_profile['names']) > 0:
                prefs.logged_in_username = user_profile['names'][0].get('displayName')
                prefs.is_logged_in = True
            else:
                self.report({'WARNING'}, "Could not retrieve user name.")

            # Inform the user of a successful exchange
            self.report({'INFO'}, "Token exchange successful. You are now logged in.")
        except Exception as e:
            # Handle exceptions during token exchange and report back to the user
            self.report({'ERROR'}, f"Failed to exchange token: {str(e)}")
            return {'CANCELLED'}
        finally:
            # Ensure the server is stopped even if the token exchange fails
            stop_server()

        return {'FINISHED'}

def stop_server():
    global httpd_server
    if httpd_server is not None:
        httpd_server.stop_server()
        httpd_server = None

# Register and unregister functions for the addon
def register():
    bpy.utils.register_class(GoogleDrivePreferences)
    bpy.utils.register_class(OAuthLoginOperator)
    bpy.utils.register_class(OAuthTokenExchangeOperator)
    bpy.app.handlers.load_post.append(stop_server)
    bpy.utils.register_class(LogoutOperator)

def unregister():
    bpy.utils.unregister_class(GoogleDrivePreferences)
    bpy.utils.unregister_class(OAuthLoginOperator)
    bpy.utils.unregister_class(OAuthTokenExchangeOperator)
    bpy.app.handlers.save_pre.remove(stop_server)
    bpy.utils.unregister_class(LogoutOperator)

if __name__ == "__main__":
    register()

bpy.app.handlers.save_pre.append(stop_server)
