import bpy
import os
import threading
import http
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser

from . import auth
from . import drive
from . import backup

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

    # Cached backup files
    _cached_backup_files = []

    def get_backup_files(self, context):
        print("Returning backup files from cache")
        print("Cached backup files:", [(file_id, file_name, "") for file_name, file_id in self._cached_backup_files])
        return [(file_id, file_name, "") for file_name, file_id in self._cached_backup_files]

    backup_files: bpy.props.EnumProperty(
        name="Available Backups",
        description="List of available backup files",
        items=get_backup_files
    )
    
    selected_backup_file_id: bpy.props.StringProperty()

    # UI for the addon preferences
    def draw(self, context):
        layout = self.layout
        prefs = bpy.context.preferences.addons[__name__].preferences

        # Display the login state and the button based on whether the user is logged in
        if prefs.is_logged_in:
            layout.operator("custom.backup", text="Backup Blender Configuration")

            layout.prop(prefs, "backup_files", text="Select Backup")
            layout.operator("custom.refresh_backup_list", text="Refresh Backup List")
            # Use the cached backup files for displaying
            for file_name, file_id in self._cached_backup_files:
                layout.label(text=file_name)
            layout.operator("custom.use_snapshot", text="Use this Snapshot")

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
        refresh_token = auth.load_refresh_token()
        if refresh_token:
            # Attempt to use the refresh token to get a new access token
            try:
                new_access_token = auth.refresh_token_flow(refresh_token)
                # Save the new access token and proceed
                auth.save_tokens(new_access_token, refresh_token)
                return {'FINISHED'}
            except TokenRefreshError:
                # Refresh token failed, proceed with full login
                pass
        
        # Start the full login process
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
                stop_server()
                return {'CANCELLED'}
            
            # Inform the user of a successful exchange
            self.report({'INFO'}, "Token exchange successful. You are now logged in.")
        except Exception as e:
            # Handle exceptions during token exchange and report back to the user
            self.report({'ERROR'}, f"Failed to exchange token: {str(e)}")
            stop_server()
            return {'CANCELLED'}
        
        # try:
        #     # backup_items = GoogleDrivePreferences.get_backup_files(context)
        #     _ = prefs.backup_files
        # except Exception as e:
        #     self.report({'ERROR'}, f"Failed to update backup files: {str(e)}")
        #     stop_server()
        #     return {'CANCELLED'}
        
        finally:
            # Ensure the server is stopped even if the token exchange fails
            stop_server()

        return {'FINISHED'}

def stop_server():
    global httpd_server
    if httpd_server is not None:
        httpd_server.stop_server()
        httpd_server = None


class BackupOperator(bpy.types.Operator):
    """Operator to handle Blender configuration backup."""
    bl_idname = "custom.backup"
    bl_label = "Backup Blender Configuration"

    def execute(self, context):
        try:
            dowloads_folder = os.path.expanduser("~/Downloads")
            backup_dir = os.path.join(dowloads_folder, "blender_backups")
            
            backup_file = backup.create_backup(backup_dir)
            access_token = bpy.context.preferences.addons[__name__].preferences.access_token
            drive.start_backup_upload(access_token, backup_file)
            self.report({'INFO'}, f"Backup created: {backup_file}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create backup: {str(e)}")
            return {'CANCELLED'}
        return {'FINISHED'}
    
class RefreshBackupListOperator(bpy.types.Operator):
    bl_idname = "custom.refresh_backup_list"
    bl_label = "Refresh Backup List"

    def execute(self, context):
        prefs = bpy.context.preferences.addons[__name__].preferences
        if prefs.is_logged_in:
            try:
                folder_id = drive.get_folder_id(prefs.access_token, 'blender')
                backup_files = drive.list_backup_files(prefs.access_token, folder_id)
                # Update the cached backup files
                prefs._cached_backup_files = backup_files
                print("Updated backup files:", prefs._cached_backup_files)
                # Manually update the EnumProperty
                bpy.context.window_manager.update_tag()
                self.report({'INFO'}, "Backup list updated.")
            except Exception as e:
                self.report({'ERROR'}, f"Failed to update backup list: {str(e)}")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "Not logged in.")
            return {'CANCELLED'}
        return {'FINISHED'}

class UseSnapshotOperator(bpy.types.Operator):
    """Operator to use the selected snapshot."""
    bl_idname = "custom.use_snapshot"
    bl_label = "Use this Snapshot"

    file_id: bpy.props.StringProperty()  # Add a property to store the selected file ID

    def execute(self, context):
        prefs = bpy.context.preferences.addons[__name__].preferences
        if prefs.is_logged_in and prefs.selected_backup_file_id:
            config_folder = backup.get_blender_config_directory()
            drive.download_and_extract_backup(prefs.access_token, prefs.selected_backup_file_id, config_folder)
            self.report({'INFO'}, "Snapshot applied successfully.")
        else:
            self.report({'ERROR'}, "Not logged in or no snapshot selected.")
        return {'FINISHED'}


# Register and unregister functions for the addon
def register():
    bpy.utils.register_class(GoogleDrivePreferences)
    bpy.utils.register_class(OAuthLoginOperator)
    bpy.utils.register_class(OAuthTokenExchangeOperator)
    bpy.app.handlers.load_post.append(stop_server)
    bpy.utils.register_class(LogoutOperator)
    bpy.utils.register_class(BackupOperator)
    bpy.utils.register_class(UseSnapshotOperator)
    bpy.utils.register_class(RefreshBackupListOperator)

def unregister():
    bpy.utils.unregister_class(GoogleDrivePreferences)
    bpy.utils.unregister_class(OAuthLoginOperator)
    bpy.utils.unregister_class(OAuthTokenExchangeOperator)
    bpy.app.handlers.save_pre.remove(stop_server)
    bpy.utils.unregister_class(LogoutOperator)
    bpy.utils.unregister_class(BackupOperator)
    bpy.utils.unregister_class(UseSnapshotOperator)
    bpy.utils.unregister_class(RefreshBackupListOperator)

if __name__ == "__main__":
    register()

bpy.app.handlers.save_pre.append(stop_server)
