import csv, os
from catboost import CatBoostClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from collections import Counter

MATCH_CSV = "match_data.csv"
MODEL_PATH = "catboost_model.cbm"

ROLE_CATEGORIES = [
    "Burst", "Bruiser AD", "Bruiser AP", "CC Tank",
    "Poke", "Sustain Mage", "Sustain Tank",
    "Assassin AD", "DPS Marksman", "Utility Support"
]

def vectorize_match(row):
    role_counts = Counter(
        [row[f"blue_{i}_role"] for i in range(1, 6)] +
        [row[f"red_{i}_role"] for i in range(1, 6)]
    )
    vector = [role_counts.get(role, 0) for role in ROLE_CATEGORIES]
    names = [row[f"blue_{i}_name"] for i in range(1, 6)] + [row[f"red_{i}_name"] for i in range(1, 6)]
    return vector + names

def load_training_data(filepath):
    X, y = [], []
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "Unknown" in [row[f"blue_{i}_role"] for i in range(1, 6)] + [row[f"red_{i}_role"] for i in range(1, 6)]:
                continue
            X.append(vectorize_match(row))
            y.append(int(row["label"]))
    return X, y

if __name__ == "__main__":
    if not os.path.exists(MODEL_PATH):
        print("모델 파일이 없습니다. 먼저 학습부터 진행하세요.")
        exit()

    X, y = load_training_data(MATCH_CSV)
    if len(X) < 50:
        print("데이터가 부족합니다. (50개 이상 필요)")
        exit()

    model = CatBoostClassifier()
    model.load_model(MODEL_PATH)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"모델 정확도: {acc:.4f} (총 데이터 수: {len(X)})")
