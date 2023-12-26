import os
import zipfile
import bpy
from datetime import datetime

def get_blender_config_directory():
    # Get the Blender version as a tuple (major, minor, subversion)
    blender_version = bpy.app.version
    # Construct the version string (e.g., "2.83")
    version_string = f"{blender_version[0]}.{blender_version[1]}"
    # Get the base user path
    user_path = bpy.utils.resource_path('USER')
    # Construct the full path to the configuration directory
    config_directory = os.path.join(user_path)
    return config_directory


def zip_directory(folder_path, zip_path):
    print(f"Zipping directory: {folder_path} to {zip_path}")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, folder_path))
                print(f"Adding file to zip: {file_path}")


def create_backup(backup_folder):
    config_folder = get_blender_config_directory()
    current_date = datetime.now().strftime("%Y%m%d")
    backup_filename = f"blender_backup_{bpy.app.version_string}_{current_date}.zip"
    
    # Ensure the backup folder exists
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    backup_path = os.path.join(backup_folder, backup_filename)
    zip_directory(config_folder, backup_path)
    return backup_path

