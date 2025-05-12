import requests, os, csv, time
from dotenv import load_dotenv
from pathlib import Path
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from collections import Counter

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": RIOT_API_KEY}

ROLE_CSV = "lol_labeling_en.csv"
MATCH_CSV = "match_data.csv"
USER_CSV = "user_list.csv"
MODEL_PATH = "catboost_model.cbm"

ROLE_CATEGORIES = [
    "Burst", "Bruiser AD", "Bruiser AP", "CC Tank",
    "Poke", "Sustain Mage", "Sustain Tank",
    "Assassin AD", "DPS Marksman", "Utility Support"
]

def normalize(name, tag):
    return name.strip().lower(), tag.strip().lower()

def get_puuid(game_name, tag_line):
    try:
        game_name = game_name.strip().encode("utf-8", "ignore").decode("utf-8")
        tag_line = tag_line.strip().encode("utf-8", "ignore").decode("utf-8")
    except Exception as e:
        print(f"[Encoding Error] game_name={game_name}, tag_line={tag_line} → {e}")
        return None

    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"

    for attempt in range(3):  
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return res.json().get("puuid")
        elif res.status_code == 429:
            print(f"[Rate Limit] {game_name}#{tag_line} → 429. Waiting... ({attempt + 1}/3)")
            time.sleep(3)
            continue 
        elif res.status_code == 404:
            print(f"[PUUID Error] {game_name}#{tag_line} → Not found. Removing from user_list.csv.")
            remove_users_from_user_list({normalize(game_name, tag_line)}, USER_CSV)
            return None
        else:
            print(f"[PUUID Error] {game_name}#{tag_line} → HTTP {res.status_code}: {res.text}")
            return None

    print(f"[Rate Limit] {game_name}#{tag_line} → Skipped after 3 retries.")
    return None

def get_match_ids(puuid, count=20, queue=450):
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}&queue={queue}"
    res = requests.get(url, headers=HEADERS)
    return res.json() if res.status_code == 200 else []

def get_match_info(match_id):
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/{match_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return None
    data = res.json()
    participants = data["info"]["participants"]
    teams = data["info"]["teams"]
    blue, red, riot_ids = [], [], []
    for p in participants:
        (blue if p["teamId"] == 100 else red).append(p["championName"])
        g, t = p.get("riotIdGameName"), p.get("riotIdTagline")
        if g and t:
            riot_ids.append(normalize(g, t))
    blue_win = next(t["win"] for t in teams if t["teamId"] == 100)
    return {
        "matchId": data["metadata"]["matchId"],
        "blueTeam": blue,
        "redTeam": red,
        "label": 1 if blue_win else 0,
        "riot_ids": riot_ids
    }

def remove_users_from_user_list(users_to_remove, filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, encoding="utf-8", errors="ignore") as f:
        all_users = list(csv.DictReader(f))
    remaining = [
        {"game_name": u["game_name"].strip(), "tag_line": u["tag_line"].strip()}
        for u in all_users
        if normalize(u.get("game_name", ""), u.get("tag_line", "")) not in users_to_remove
    ]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["game_name", "tag_line"])
        writer.writeheader()
        writer.writerows(remaining)

def load_role_labels(path):
    with open(path, encoding="utf-8") as f:
        return {row["champion_name"]: row["role_group"] for row in csv.DictReader(f)}

def load_saved_match_ids(path):
    if not os.path.exists(path): return set()
    with open(path, encoding="utf-8") as f:
        return {row["match_id"] for row in csv.DictReader(f)}

def append_match(filepath, match, role_map):
    bnames, rnames = match["blueTeam"], match["redTeam"]
    broles = [role_map.get(c, "Unknown") for c in bnames]
    rroles = [role_map.get(c, "Unknown") for c in rnames]
    if "Unknown" in broles + rroles:
        return
    row = [match["matchId"]] + [item for pair in zip(bnames, broles) for item in pair] + \
          [item for pair in zip(rnames, rroles) for item in pair] + [match["label"]]
    write_header = not os.path.exists(filepath)
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            header = ["match_id"] + [f"blue_{i}_{k}" for i in range(1,6) for k in ("name", "role")] + \
                     [f"red_{i}_{k}" for i in range(1,6) for k in ("name", "role")] + ["label"]
            writer.writerow(header)
        writer.writerow(row)

def vectorize_match(row):
    role_counts = Counter([row[f"blue_{i}_role"] for i in range(1,6)] + [row[f"red_{i}_role"] for i in range(1,6)])
    vector = [role_counts.get(role, 0) for role in ROLE_CATEGORIES]
    names = [row[f"blue_{i}_name"] for i in range(1,6)] + [row[f"red_{i}_name"] for i in range(1,6)]
    return vector + names

def load_training_data(filepath):
    X, y = [], []
    with open(filepath, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "Unknown" in [row[f"blue_{i}_role"] for i in range(1,6)] + [row[f"red_{i}_role"] for i in range(1,6)]:
                continue
            X.append(vectorize_match(row))
            y.append(int(row["label"]))
    return X, y

if __name__ == "__main__":
    role_map = load_role_labels(ROLE_CSV)
    saved_ids = load_saved_match_ids(MATCH_CSV)

    try:
        with open(USER_CSV, encoding="utf-8", errors="ignore") as f:
            users = list(csv.DictReader(f))

        for user in users:
            try:
                puuid = get_puuid(user["game_name"], user["tag_line"])
                if not puuid:
                    print(f"PUUID not found for {user['game_name']}#{user['tag_line']}")
                    continue

                valid_match_count = 0
                match_ids = get_match_ids(puuid, count=20)
                for match_id in match_ids:
                    if match_id in saved_ids:
                        continue
                    match = get_match_info(match_id)
                    if match:
                        append_match(MATCH_CSV, match, role_map)
                        saved_ids.add(match["matchId"])
                        valid_match_count += 1

                if valid_match_count >= 10:
                    remove_users_from_user_list({normalize(user["game_name"], user["tag_line"])}, USER_CSV)
            except Exception as user_error:
                print(f"[User Error] {user.get('game_name')}#{user.get('tag_line')} → {user_error}")

    except Exception as file_error:
        print(f"[File Error] Failed to load users → {file_error}")

    try:
        X, y = load_training_data(MATCH_CSV)
        if len(X) < 50:
            print("Not enough data to train. (need 50+ matches)")
        else:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            cat_features = list(range(10, 20))
            model = CatBoostClassifier(verbose=0)
            model.fit(X_train, y_train, cat_features=cat_features)
            model.save_model(MODEL_PATH)
            acc = accuracy_score(y_test, model.predict(X_test))
            with open("train_log.txt", "a", encoding="utf-8") as log:
                log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Accuracy: {acc:.4f} on {len(X)} matches\n")
    except Exception as train_error:
        print(f"[Training Error] {train_error}")