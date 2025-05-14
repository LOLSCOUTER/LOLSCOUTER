import csv
from collections import Counter

MATCH_CSV = "match_data.csv"

def load_labels(filepath):
    labels = []
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get("label")
            if label in ("0", "1"):
                labels.append(int(label))
    return labels

if __name__ == "__main__":
    y = load_labels(MATCH_CSV)
    count = Counter(y)
    
    print(f"레드팀 승 (0): {count[0]}")
    print(f"블루팀 승 (1): {count[1]}")
    print(f"총 데이터 수: {sum(count.values())}")
