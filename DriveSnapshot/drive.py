import requests
import threading
import json
import os
import zipfile
import bpy

# Define a function to get user's profile information using the Google People API
def get_user_profile(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }
    people_api_url = 'https://people.googleapis.com/v1/people/me?personFields=names,emailAddresses'
    response = requests.get(people_api_url, headers=headers)
    response.raise_for_status()
    
    user_info = response.json()
    print("People API response:", user_info)  # For debugging purposes

    return user_info

def get_folder_id(access_token, folder_name):
    """Get the ID of the folder with the given name, or create it if it doesn't exist."""
    headers = {'Authorization': 'Bearer ' + access_token}
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
    response = requests.get('https://www.googleapis.com/drive/v3/files?q=' + query, headers=headers)
    response.raise_for_status()
    folders = response.json().get('files', [])

    if folders:
        return folders[0]['id']
    else:
        # Create the folder
        metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        response = requests.post('https://www.googleapis.com/drive/v3/files', headers=headers, json=metadata)
        response.raise_for_status()
        return response.json()['id']

def upload_file(access_token, file_path, folder_id):
    """Upload a file to the specified folder on Google Drive."""
    headers = {'Authorization': 'Bearer ' + access_token}
    
    # Correctly extract just the file name from the file path
    file_name = os.path.basename(file_path)
    metadata = {'name': file_name, 'parents': [folder_id]}

    files = {
        'data': ('metadata', json.dumps(metadata), 'application/json'),
        'file': open(file_path, 'rb')
    }
    response = requests.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart', headers=headers, files=files)
    response.raise_for_status()

def upload_backup(access_token, file_path):
    """Upload the backup file to a 'blender' folder in Google Drive."""
    folder_id = get_folder_id(access_token, 'blender')
    upload_file(access_token, file_path, folder_id)

def start_backup_upload(access_token, file_path):
    """Start the backup upload in a background thread."""
    threading.Thread(target=upload_backup, args=(access_token, file_path), daemon=True).start()

def list_backup_files(access_token, folder_id):
    """List all backup files in the specified Google Drive folder."""
    headers = {'Authorization': 'Bearer ' + access_token}
    query = f"'{folder_id}' in parents and mimeType='application/zip'"
    response = requests.get(f'https://www.googleapis.com/drive/v3/files?q={query}', headers=headers)
    response.raise_for_status()
    
    files = response.json().get('files', [])
    return [(file['name'], file['id']) for file in files]

def update_backup_files(context):
    prefs = bpy.context.preferences.addons[__name__].preferences
    if prefs.is_logged_in:
        try:
            folder_id = get_folder_id(prefs.access_token, 'blender')
            backup_files = list_backup_files(prefs.access_token, folder_id)
            # Update the EnumProperty items
            prefs.backup_files = [(file_id, file_name, "") for file_name, file_id in backup_files]
        except Exception as e:
            print("Failed to update backup files:", str(e))


def download_and_extract_backup(access_token, file_id, destination_folder):
    """Download and extract a backup file from Google Drive."""
    headers = {'Authorization': 'Bearer ' + access_token}
    response = requests.get(f'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media', headers=headers, stream=True)
    response.raise_for_status()

    zip_file_path = os.path.join(destination_folder, "temp_backup.zip")
    with open(zip_file_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=128):
            f.write(chunk)

    # Extract the zip file
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(destination_folder)

    os.remove(zip_file_path)  # Clean up the temporary zip file
