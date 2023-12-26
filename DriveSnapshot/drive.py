import requests
import threading
import json

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
    metadata = {'name': file_path.split('/')[-1], 'parents': [folder_id]}
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