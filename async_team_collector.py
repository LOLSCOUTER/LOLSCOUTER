import os, csv, asyncio, aiohttp, time
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

API_KEY = os.getenv("RIOT_API_KEY")
SEED_GAME_NAME = os.getenv("SEED_GAME_NAME")
SEED_TAG_LINE = os.getenv("SEED_TAG_LINE")
HEADERS = {"X-Riot-Token": API_KEY}
ROLE_CSV = "lol_labeling_en.csv"
TEAM_CSV = "team_data.csv"

ROLE_CATEGORIES = [
    "Burst", "Bruiser AD", "Bruiser AP", "CC Tank",
    "Poke", "Sustain Mage", "Sustain Tank",
    "Assassin AD", "DPS Marksman", "Utility Support"
]

def normalize_name(name):
    return name.strip().lower()

def load_role_map():
    with open(ROLE_CSV, encoding="utf-8") as f:
        return {row["champion_name"]: row["role_group"] for row in csv.DictReader(f)}

def load_saved_pairs():
    saved = set()
    if not os.path.exists(TEAM_CSV):
        return saved
    with open(TEAM_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 6:
                match_id = row[0]
                team_hash = ",".join(sorted(row[1:6]))
                key = f"{match_id}_{team_hash}"
                saved.add(key)
    return saved

def save_team(match_id, champs, roles, label):
    write_header = not os.path.exists(TEAM_CSV)
    with open(TEAM_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            header = ["match_id"] + [f"champ_{i}" for i in range(1, 6)] + [f"role_{i}" for i in range(1, 6)] + ["label"]
            writer.writerow(header)
        writer.writerow([match_id] + champs + roles + [label])

semaphore = asyncio.Semaphore(10) 

async def safe_get(session, url):
    async with semaphore:
        for _ in range(3):
            try:
                async with session.get(url, headers=HEADERS) as res:
                    if res.status == 200:
                        return await res.json()
                    elif res.status == 429:
                        retry_after = float(res.headers.get("Retry-After", 1.5))
                        await asyncio.sleep(retry_after)
                    else:
                        return None
            except Exception:
                await asyncio.sleep(1)
    return None

async def get_puuid(session, game_name, tag_line):
    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    data = await safe_get(session, url)
    return data.get("puuid") if data else None

async def get_match_ids(session, puuid, count=10):
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}&queue=450"
    return await safe_get(session, url) or []

async def get_match_detail(session, match_id):
    url = f"https://asia.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return await safe_get(session, url)

def process_match(match, role_map, saved_pairs):
    participants = match["info"]["participants"]
    team_champs = defaultdict(list)
    team_roles = defaultdict(list)

    for p in participants:
        champ = p["championName"]
        team_id = p["teamId"]
        team_champs[team_id].append(champ)
        team_roles[team_id].append(role_map.get(champ, "Unknown"))

    if all(len(team_champs[t]) == 5 and "Unknown" not in team_roles[t] for t in [100, 200]):
        match_id = match["metadata"]["matchId"]
        for team_id, win_idx in zip([100, 200], [0, 1]):
            champs = team_champs[team_id]
            roles = team_roles[team_id]
            key = f"{match_id}_{','.join(sorted(champs))}"
            if key in saved_pairs:
                continue
            save_team(match_id, champs, roles, int(match["info"]["teams"][win_idx]["win"]))
            saved_pairs.add(key)

async def loop_collect(seed_game, seed_tag):
    saved_pairs = load_saved_pairs()
    role_map = load_role_map()
    global_visited = set()

    while True:
        queue = [(seed_game, seed_tag)]
        visited = set()

        async with aiohttp.ClientSession() as session:
            while queue and len(visited) < 200:
                game_name, tag_line = queue.pop(0)
                key = (normalize_name(game_name), normalize_name(tag_line))
                if key in visited or key in global_visited:
                    continue
                visited.add(key)
                global_visited.add(key)

                puuid = await get_puuid(session, game_name, tag_line)
                if not puuid:
                    continue

                match_ids = await get_match_ids(session, puuid)
                detail_tasks = [get_match_detail(session, mid) for mid in match_ids]
                match_list = await asyncio.gather(*detail_tasks)

                for match in filter(None, match_list):
                    process_match(match, role_map, saved_pairs)
                    for p in match["info"]["participants"]:
                        g, t = p.get("riotIdGameName"), p.get("riotIdTagline")
                        if g and t:
                            queue.append((g, t))

        print(f"\n [{time.strftime('%H:%M:%S')}] Saved so far: {len(saved_pairs)} — 재시작\n")

if __name__ == "__main__":
    asyncio.run(loop_collect(SEED_GAME_NAME, SEED_TAG_LINE))