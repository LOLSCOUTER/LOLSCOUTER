import requests
import os
import csv
import random
from dotenv import load_dotenv
from pathlib import Path
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

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

def get_match_info(match_id):
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/{match_id}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"[MATCH DETAIL ERROR] {response.status_code}: {response.text}")
        return None

    data = response.json()
    participants = data["info"]["participants"]

    blue_team = []
    red_team = []

    for p in participants:
        if p["teamId"] == 100:
            blue_team.append(p["championName"])
        elif p["teamId"] == 200:
            red_team.append(p["championName"])

    return {
        "matchId": match_id,
        "blueTeam": blue_team,
        "redTeam": red_team
    }

def load_role_labels(filepath):
    role_map = {}
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            role_map[row['champion_name']] = row['role_group']
    return role_map

def convert_champions_to_roles(champ_list, role_map):
    return [role_map.get(champ, "Unknown") for champ in champ_list]

def create_training_data(match_data, role_map):
    X = []
    y = []
    for match in match_data:
        blue_roles = convert_champions_to_roles(match["blueTeam"], role_map)
        red_roles = convert_champions_to_roles(match["redTeam"], role_map)
        if "Unknown" in blue_roles or "Unknown" in red_roles:
            continue
        features = blue_roles + red_roles
        label = random.choice([0, 1])
        X.append(features)
        y.append(label)
    return X, y

if __name__ == "__main__":
    game_name = os.getenv("RIOT_GAME_NAME")
    tag_line = os.getenv("RIOT_TAG_LINE")
    
    puuid = get_puuid(game_name, tag_line)
    print("PUUID:", puuid)

    if puuid:
        match_ids = get_match_ids(puuid)
        print("Match IDs:", match_ids)

        match_data = []
        for mid in match_ids:
            info = get_match_info(mid)
            if info:
                match_data.append(info)

        print("Sample Match Detail:", match_data[0] if match_data else "No match data")

        role_map = load_role_labels("lol_labeling_en.csv")
        X, y = create_training_data(match_data, role_map)

        print("Sample X:", X[0] if X else "None")
        print("Sample y:", y[0] if y else "None")

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = CatBoostClassifier(verbose=0)
        model.fit(X_train, y_train, cat_features=list(range(10)))

        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        print("Accuracy on test set:", accuracy)
