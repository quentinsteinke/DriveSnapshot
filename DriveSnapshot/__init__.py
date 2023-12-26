import bpy
from . import auth
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

# OAuth local server settings
LOCAL_SERVER_PORT = 8080
LOCAL_SERVER_HOST = 'localhost'
REDIRECT_URI = f'http://{LOCAL_SERVER_HOST}:{LOCAL_SERVER_PORT}/'

# Define the addon's preferences here
class GoogleDrivePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    # Temporary in-memory storage for the code verifier
    code_verifier = bpy.props.StringProperty(default="")

    # UI for the addon preferences
    def draw(self, context):
        layout = self.layout
        layout.operator("custom.oauth_login")

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
        httpd = StoppableHTTPServer((LOCAL_SERVER_HOST, LOCAL_SERVER_PORT), OAuthLocalServerHandler)
        bpy.types.WindowManager.oauth_httpd = httpd  # Correctly store the server reference
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

    def stop_local_server(self):
        # Call this method when you want to stop the server
        if self.server:
            self.server.stop_server()

class OAuthTokenExchangeOperator(bpy.types.Operator):
    """Operator to handle token exchange after receiving the authorization code."""
    bl_idname = "custom.oauth_token_exchange"
    bl_label = "Exchange Authorization Code for Token"
    authorization_code: bpy.props.StringProperty()

    def execute(self, context):
        prefs = bpy.context.preferences.addons[__name__].preferences
        token_data = auth.exchange_code_for_token(prefs.code_verifier, self.authorization_code)
        # Here you would securely store the token_data and handle any errors
        # For example, you might encrypt the tokens and store them in a secure location
        # If storing tokens in preferences, make sure to obfuscate or encrypt them
        # ...
        # Properly handle any errors that may have occurred and report back to the user
        return {'FINISHED'}

def stop_server():
    wm = bpy.context.window_manager
    if hasattr(wm, 'oauth_httpd'):
        wm.oauth_httpd.stop_server()
        delattr(wm, 'oauth_httpd')

# Register and unregister functions for the addon
def register():
    bpy.utils.register_class(GoogleDrivePreferences)
    bpy.utils.register_class(OAuthLoginOperator)
    bpy.utils.register_class(OAuthTokenExchangeOperator)
    bpy.app.handlers.load_post.append(stop_server)

def unregister():
    bpy.utils.unregister_class(GoogleDrivePreferences)
    bpy.utils.unregister_class(OAuthLoginOperator)
    bpy.utils.unregister_class(OAuthTokenExchangeOperator)
    bpy.app.handlers.load_post.remove(stop_server)

if __name__ == "__main__":
    register()

bpy.app.handlers.save_pre.append(stop_server)
