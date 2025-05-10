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
        print(f"[PUUID ERROR] {response.status_code}: {response.text}")
        return None

def get_match_ids(puuid, count=20, queue=450):
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}&queue={queue}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[MATCH ID ERROR] {response.status_code}: {response.text}")
        return []

if __name__ == "__main__":
    game_name = os.getenv("RIOT_GAME_NAME")
    tag_line = os.getenv("RIOT_TAG_LINE")

    
    puuid = get_puuid(game_name, tag_line)
    print("PUUID:", puuid)

    if puuid:
        match_ids = get_match_ids(puuid)
        print("Match IDs:", match_ids)
