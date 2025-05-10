import requests
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
print("KEY:", RIOT_API_KEY) 

headers = {"X-Riot-Token": RIOT_API_KEY}

def get_puuid(game_name, tag_line):
    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("puuid")
    else:
        print(f"Error {response.status_code}: {response.text}")
        return None

puuid = get_puuid("hideonbush", "KR1")
print("PUUID:", puuid)
