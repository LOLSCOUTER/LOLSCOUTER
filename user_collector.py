import requests, os, csv, random, time
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}
USER_CSV = "user_list.csv"

def normalize(name, tag):
    return name.strip().lower(), tag.strip().lower()

def remove_users_from_user_list(users_to_remove, filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, encoding="utf-8", errors="ignore") as f:
        all_users = list(csv.DictReader(f))
    remaining = []
    for u in all_users:
        gn = u.get("game_name", "").strip()
        tg = u.get("tag_line", "").strip()
        if not gn or not tg:
            continue
        if normalize(gn, tg) not in users_to_remove:
            remaining.append({"game_name": gn, "tag_line": tg})
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["game_name", "tag_line"])
        writer.writeheader()
        writer.writerows(remaining)

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

def get_recent_match_ids(puuid, count=10):
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}&queue=450"
    res = requests.get(url, headers=HEADERS)
    return res.json() if res.status_code == 200 else []

def get_riot_ids_from_match(match_id):
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/{match_id}"
    res = requests.get(url, headers=HEADERS)
    if res.status_code != 200:
        return []
    try:
        participants = res.json()["info"]["participants"]
        return [
            {"game_name": p["riotIdGameName"], "tag_line": p["riotIdTagline"]}
            for p in participants
            if p.get("riotIdGameName") and p.get("riotIdTagline")
        ]
    except:
        return []

def load_existing_users(filepath):
    existing = set()
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["game_name"].strip().lower(), row["tag_line"].strip().lower())
                existing.add(key)
    return existing

def is_valid_user(user):
    return (
        isinstance(user.get("game_name"), str) and user["game_name"].strip() and
        isinstance(user.get("tag_line"), str) and user["tag_line"].strip()
    )

def save_users(new_users, filepath):
    existing = load_existing_users(filepath)
    new_entries = [
        u for u in new_users
        if is_valid_user(u) and (u["game_name"].strip().lower(), u["tag_line"].strip().lower()) not in existing
    ]
    if not new_entries:
        print("신규 유저 없음")
        return
    write_header = not os.path.exists(filepath)
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["game_name", "tag_line"])
        if write_header:
            writer.writeheader()
        writer.writerows({
            "game_name": u["game_name"].strip(),
            "tag_line": u["tag_line"].strip()
        } for u in new_entries)
    print(f"user_list.csv에 {len(new_entries)}명 추가")

if __name__ == "__main__":
    if not os.path.exists(USER_CSV):
        print("user_list.csv가 없습니다. 최소 한 명의 유저를 수동으로 추가하세요.")
        exit()

    with open(USER_CSV, encoding="utf-8") as f:
        users = list(csv.DictReader(f))

    if not users:
        print("user_list.csv에 유저가 없습니다.")
        exit()

    seed = random.choice(users)
    seed_puuid = get_puuid(seed["game_name"], seed["tag_line"])

    if not seed_puuid:
        print("Seed PUUID 조회 실패")
        exit()

    match_ids = get_recent_match_ids(seed_puuid)
    print(f"{seed['game_name']} 최근 매치 {len(match_ids)}개 수집")

    all_new_users = []
    for mid in match_ids:
        all_new_users.extend(get_riot_ids_from_match(mid))

    save_users(all_new_users, USER_CSV)
