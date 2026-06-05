total = 0
for _, row in df.iterrows():
    if row["age"] > 30:
        total += row["salary"]
