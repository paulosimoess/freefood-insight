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

def estimate_calories_from_objects(objects: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], float]:
    kcal_base = load_kcal_base()
    items: List[Dict[str, Any]] = []
    total = 0.0

    for obj in objects:
        name = obj.get("label_name")
        conf = _norm_conf(obj.get("confidence", 0.0))
        if not name or name in NON_FOOD:
            continue

        base = kcal_base.get(name, 0.0)
        kcal = round(base * conf, 2)

        items.append({
            "label_name": name,
            "confidence": round(conf, 4),
            "kcal_base": base,
            "kcal_estimated": kcal,
        })
        total += kcal

    return items, round(total, 2)
