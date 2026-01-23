import json
import os
from typing import Dict, Any, List, Tuple

NON_FOOD = {"plate", "knife", "fork", "spoon", "bowl", "cup"}

def load_kcal_base() -> Dict[str, float]:
    here = os.path.dirname(__file__)
    path = os.path.join(here, "calorie_map.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: float(v) for k, v in data.items()}

def _norm_conf(conf: Any) -> float:
    try:
        c = float(conf)
    except Exception:
        return 0.0
    if c > 1.0:
        c /= 100.0
    return max(0.0, min(1.0, c))

def estimate_calories_from_objects(
    objects: List[Dict[str, Any]],
    plate_area: float,
    garbage_area: float = 0.0,
    grams_per_plate: float = 500.0,
) -> Tuple[List[Dict[str, Any]], float]:

    kcal_base = load_kcal_base()  # kcal por 100g
    items: List[Dict[str, Any]] = []
    total = 0.0

    plate_usable = max(1.0, float(plate_area) - float(garbage_area))

    for obj in objects:
        name = obj.get("label_name")
        conf = _norm_conf(obj.get("confidence", 0.0))
        area = float(obj.get("area", 0.0) or 0.0)

        if not name or name in NON_FOOD:
            continue

        kcal_100g = float(kcal_base.get(name, 0.0))
        if kcal_100g <= 0 or area <= 0:
            # sem kcal definida ou sem área -> não estima
            continue

        portion_ratio = max(0.0, min(1.0, area / plate_usable))
        grams_est = portion_ratio * float(grams_per_plate)

        kcal_raw = (kcal_100g / 100.0) * grams_est
        kcal_final = round(kcal_raw * conf, 2)

        items.append({
            "label_name": name,
            "confidence": round(conf, 4),
            "area": round(area, 2),
            "portion_ratio": round(portion_ratio, 4),
            "grams_est": round(grams_est, 1),
            "kcal_per_100g": round(kcal_100g, 2),
            "kcal_estimated": kcal_final,
            "formula": "(kcal_100g/100)*grams_est*confidence"
        })
        total += kcal_final

    return items, round(total, 2)
