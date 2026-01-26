import json
import os
from typing import Dict, Any, List, Tuple

# Tudo o que não deve entrar na estimativa
NON_FOOD = {
    "plate", "knife", "fork", "spoon", "bowl", "cup",
    "garbage", "board", "water", "coffee", "coffee cup", "water cup"
}

# Correções manuais (prioridade máxima) para evitar valores absurdos do CSV (ex: arroz cru)
OVERRIDES_KCAL_100G = {
    "rice": 130.0,
    "strawberry": 32.0,
    "vegetables": 35.0,
    "soup": 60.0,
}

# Limites de sanidade (evitar porções absurdas por causa das boxes)
MAX_PORTION = 0.70       # máximo 70% do prato por item
MAX_GRAMS_ITEM = 350.0   # máximo gramas por item
MIN_GRAMS_ITEM = 10.0    # mínimo para ignorar ruído (opcional)
MIN_CONF = 0.15          # ignora deteções muito fracas (opcional)

# Quantidade típica (g) se o prato fosse 100% daquele alimento
FULL_PLATE_GRAMS = {
    "rice": 450.0,
    "pasta": 400.0,
    "french fries": 300.0,
    "chips": 300.0,
    "steak": 280.0,
    "grilled steak": 280.0,
    "grilled chop": 250.0,
    "vegetables": 250.0,
    "lettuce": 200.0,
    "soup": 350.0,
}
DEFAULT_FULL_PLATE_GRAMS = 400.0


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
    grams_per_plate: float = 500.0,  # usado como fallback/default
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

        # opcional: filtra deteções muito fracas
        if conf < MIN_CONF:
            continue

        kcal_100g = OVERRIDES_KCAL_100G.get(name, kcal_base.get(name, 0.0))
        if kcal_100g <= 0 or area <= 0:
            continue

        # Porção (área relativa ao prato) + limites de sanidade
        portion_ratio = area / plate_usable
        portion_ratio = max(0.0, min(MAX_PORTION, portion_ratio))

        # "Prato cheio" por alimento (ou fallback do parâmetro)
        full_plate = FULL_PLATE_GRAMS.get(name, float(grams_per_plate) or DEFAULT_FULL_PLATE_GRAMS)
        grams_est = portion_ratio * full_plate
        grams_est = max(MIN_GRAMS_ITEM, min(MAX_GRAMS_ITEM, grams_est))

        kcal_raw = (kcal_100g / 100.0) * grams_est
        kcal_final = round(kcal_raw, 2)

        items.append({
            "label_name": name,
            "confidence": round(conf, 4),
            "area": round(area, 2),
            "portion_ratio": round(portion_ratio, 4),
            "grams_est": round(grams_est, 1),
            "kcal_per_100g": round(kcal_100g, 2),
            "kcal_estimated": kcal_final,
            "formula": "(kcal_100g/100)*grams_est"
        })
        total += kcal_final

    return items, round(total, 2)
