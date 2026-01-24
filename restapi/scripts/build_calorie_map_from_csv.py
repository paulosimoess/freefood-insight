import sys
sys.path.insert(0, "/app")

import csv, json, re
from server.yolo.yolo import YOLOModel

CSV_PATH = "/app/data/nutrition.csv"
OUT_PATH = "/app/calorie_map.json"

NON_FOOD = {"plate","fork","knife","spoon","bowl","cup","coffee cup","water cup","board","garbage","soupbowl","water","coffee"}

PREFER = {
    "banana": ["raw", "fresh"],
    "apple": ["raw", "fresh"],
    "strawberry": ["raw", "fresh"],
    "grape": ["raw", "fresh"],
    "melon": ["raw", "fresh"],
    "watermelon": ["raw", "fresh"],
    "tomato": ["raw", "fresh"],
    "lettuce": ["raw", "fresh"],
    "cucumber": ["raw", "fresh"],
    "onion": ["raw", "fresh"],
    "lime": ["raw", "fresh"],
    "pineapple": ["raw", "fresh"],

    "rice": ["cooked"],
    "pasta": ["cooked"],
    "spaghetti": ["cooked"],
    "french fries": ["fried"],
    "chips": ["fried"],
    "pizza": ["pizza"],
    "lasagna": ["lasagna"],
    "chicken": ["cooked", "roasted", "grilled"],
    "pork": ["cooked", "roasted", "grilled"],
    "salmon": ["cooked", "baked", "grilled"],
    "tuna": ["cooked"],
    "omelet": ["cooked"],
    "boiled egg": ["boiled"],
    "fried egg": ["fried"],
}

AVOID = [
    "dried", "dehydrated", "sweetened", "in syrup", "candied",
    "with sugar", "sugar added", "powder", "mix", "supplement"
]

def parse_kcal(x: str):
    if x is None:
        return None
    m = re.search(r"([\d.]+)", str(x))
    return float(m.group(1)) if m else None

def score_text(text: str, label: str):
    t = (text or "").lower()
    score = 0

    for bad in AVOID:
        if bad in t:
            score -= 50

    for p in PREFER.get(label, []):
        if p.lower() in t:
            score += 20

    # pequenos boosts
    if "raw" in t or "fresh" in t:
        score += 2
    if any(k in t for k in ("cooked","grilled","roasted","baked","fried","boiled")):
        score += 2

    # match por palavra
    if re.search(rf"\b{re.escape(label.lower())}\b", t):
        score += 5

    return score

def load_rows():
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        cols = [c.strip() for c in reader.fieldnames or []]
        # encontrar colunas prováveis
        name_col = None
        cal_col = None
        for c in cols:
            cl = c.lower()
            if name_col is None and cl in ("item","name","food","description"):
                name_col = c
            if cal_col is None and "cal" in cl:
                cal_col = c
        if not name_col or not cal_col:
            raise RuntimeError(f"Não consegui inferir colunas. Tenho: {cols}")

        rows = []
        for r in reader:
            name = (r.get(name_col) or "").strip()
            kcal = parse_kcal(r.get(cal_col))
            if not name or kcal is None:
                continue
            rows.append((name, kcal))
        return rows

def best_kcal_for_label(rows, label: str):
    label_l = label.lower()

    # candidatos: match por palavra (melhor), fallback substring
    word_pat = re.compile(rf"\b{re.escape(label_l)}\b", re.IGNORECASE)
    cands = [(name, kcal) for (name, kcal) in rows if word_pat.search(name)]
    if not cands:
        cands = [(name, kcal) for (name, kcal) in rows if label_l in name.lower()]
        if not cands:
            return None

    # escolher por score
    best = None
    best_score = -10**9
    for name, kcal in cands:
        sc = score_text(name, label)
        # tie-break: kcal maior (não é perfeito, mas ok)
        if sc > best_score or (sc == best_score and best and kcal > best[1]):
            best = (name, kcal)
            best_score = sc

    if best_score < -10:
        return None
    return best[1]

def main():
    rows = load_rows()

    m = YOLOModel()
    names = getattr(m.model, "names", {})
    labels = [names[k] for k in sorted(names.keys())]

    out = {}
    for label in labels:
        if label in NON_FOOD:
            out[label] = 0
            continue
        kcal = best_kcal_for_label(rows, label)
        out[label] = round(float(kcal), 2) if kcal is not None else 0

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    filled = sum(1 for v in out.values() if v and v > 0)
    print("Gerado:", OUT_PATH)
    print("Labels:", len(out), "| Com kcal:", filled)
    print("Exemplos -> banana:", out.get("banana"), "rice:", out.get("rice"), "french fries:", out.get("french fries"))

if __name__ == "__main__":
    main()
