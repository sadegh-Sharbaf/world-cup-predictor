import http.client
import json
import requests

# تنظیمات اصلی
API_KEY = "00aa0d0aae6d94bb70304ed77d213d78"
LEAGUE_ID = 1

import requests

headers = {
"x-apisports-key": API_KEY
}

response = requests.get(
"https://v3.football.api-sports.io/status",
headers=headers,
timeout=20,
verify=False
)

print(response.status_code)
print(response.text)



headers = {
    "x-apisports-key": API_KEY
}

response = requests.get(
    "https://v3.football.api-sports.io/leagues",
    headers=headers,
    params={"search": "World Cup"},
    verify=False
)

print(response.status_code)
print(response.json())




headers = {
    "x-apisports-key": API_KEY
}

response = requests.get(
    "https://v3.football.api-sports.io/fixtures",
    headers=headers,
    params={
        "league": 1,
        "season": 2026
    },
    verify=False
)

print(response.status_code)
print(response.json())



response = requests.get(
    "https://v3.football.api-sports.io/fixtures",
    headers={"x-apisports-key": API_KEY},
    params={
        "league": 1,
        "season": 2022
    },
    verify=False
)

print(response.status_code)
print(response.json())