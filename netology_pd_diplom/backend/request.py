import requests

api_url = 'http://127.0.0.1:8000/api/v1/shops'
# auth_token = ""
data = {
    # "state": "on"
}

headers = {
    # 'Authorization': f'Token {auth_token}',
    'Content-Type': 'application/json'
}

response = requests.get(api_url, headers=headers, json=data)
print(response.text)