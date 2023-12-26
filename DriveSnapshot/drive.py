import requests

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