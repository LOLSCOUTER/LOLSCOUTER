import pandas as pd
from collections import Counter

df = pd.read_csv("match_data.csv")

roles = []
for i in range(1, 6):
    roles += df[f"blue_{i}_role"].tolist()
    roles += df[f"red_{i}_role"].tolist()

role_counts = Counter(roles)
for role, count in role_counts.items():
    print(f"{role}: {count}")
