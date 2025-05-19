import os, csv, time
from dotenv import load_dotenv
from pathlib import Path
from collections import Counter
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from catboost import CatBoostClassifier
from xgboost import XGBClassifier
import warnings

warnings.filterwarnings("ignore")

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

TEAM_CSV = "team_data.csv"
CATBOOST_MODEL_PATH = "catboost_team_model.cbm"
XGBOOST_MODEL_PATH = "xgboost_team_model.json"

ROLE_CATEGORIES = [
    "Burst", "Bruiser AD", "Bruiser AP", "CC Tank",
    "Poke", "Sustain Mage", "Sustain Tank",
    "Assassin AD", "DPS Marksman", "Utility Support"
]

def featurize_team(row):
    role_counts = Counter([row[f"role_{i}"] for i in range(1, 6)])
    role_vector = [role_counts.get(role, 0) for role in ROLE_CATEGORIES]
    ad_roles = {"Bruiser AD", "Assassin AD", "DPS Marksman"}
    ap_roles = {"Burst", "Bruiser AP", "Sustain Mage", "Poke"}
    utility_roles = {"Utility Support"}
    tank_roles = {"Sustain Tank", "CC Tank"}
    ad_count = sum(1 for i in range(1, 6) if row[f"role_{i}"] in ad_roles)
    ap_count = sum(1 for i in range(1, 6) if row[f"role_{i}"] in ap_roles)
    utility_count = sum(1 for i in range(1, 6) if row[f"role_{i}"] in utility_roles)
    tank_count = sum(1 for i in range(1, 6) if row[f"role_{i}"] in tank_roles)
    diversity = len(set([row[f"role_{i}"] for i in range(1, 6)]))
    return role_vector + [ad_count, ap_count, utility_count, tank_count, diversity]

def load_training_data(filepath):
    X, y = [], []
    with open(filepath, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "Unknown" in [row[f"role_{i}"] for i in range(1, 6)]:
                continue
            X.append(featurize_team(row))
            y.append(int(row["label"]))
    return X, y

def evaluate_model(model, X_test, y_test):
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    f1 = f1_score(y_test, preds, zero_division=0)
    precision = precision_score(y_test, preds, zero_division=0)
    recall = recall_score(y_test, preds, zero_division=0)
    return acc, f1, precision, recall

if __name__ == "__main__":
    try:
        X, y = load_training_data(TEAM_CSV)
        if len(X) < 50:
            print("데이터가 충분하지 않습니다.")
            exit()

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        cat_model = CatBoostClassifier(verbose=0)
        cat_model.fit(X_train, y_train)
        cat_model.save_model(CATBOOST_MODEL_PATH)
        acc_c, f1_c, p_c, r_c = evaluate_model(cat_model, X_test, y_test)

        xgb_model = XGBClassifier(use_label_encoder=False, eval_metric='logloss')
        xgb_model.fit(X_train, y_train)
        xgb_model.save_model(XGBOOST_MODEL_PATH)
        acc_x, f1_x, p_x, r_x = evaluate_model(xgb_model, X_test, y_test)

        now = time.strftime('%Y-%m-%d %H:%M:%S')
        with open("train_log.txt", "a", encoding="utf-8") as log:
            log.write(f"[{now}] CatBoost → acc: {acc_c:.4f}, f1: {f1_c:.4f}, precision: {p_c:.4f}, recall: {r_c:.4f}, data: {len(X)}\n")
            log.write(f"[{now}] XGBoost  → acc: {acc_x:.4f}, f1: {f1_x:.4f}, precision: {p_x:.4f}, recall: {r_x:.4f}, data: {len(X)}\n")

        print(f"CatBoost accuracy: {acc_c:.4f} | XGBoost accuracy: {acc_x:.4f}")

    except Exception as e:
        print(f"[Training Error] {e}")
