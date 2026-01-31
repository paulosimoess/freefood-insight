import json
import os
from typing import Dict, Any, List, Tuple

NON_FOOD = {
    "plate", "knife", "fork", "spoon", "bowl", "cup",
    "garbage", "board", "water", "coffee", "coffee cup", "water cup"
}

# Correções manuais para evitar valores absurdos do CSV
OVERRIDES_KCAL_100G = {
    "rice": 130.0,
    "strawberry": 32.0,
    "vegetables": 35.0,
    "soup": 60.0,
    "chicken": 190.0,  # CSV tinha 462/100g -> absurdo
}

# cortar falsos positivos específicos
MIN_CONF_BY_CLASS = {
    "pasta": 0.15,  # falsos positivos -> molhos / massas “fantasma”
    "soup": 0.25,   # falsos positivos -> molhos
}

# Limites de sanidade
MAX_PORTION = 0.70       # máximo 70% do prato por item
MAX_GRAMS_ITEM = 350.0   # máximo gramas por item
MIN_GRAMS_ITEM = 10.0    # mínimo para ignorar ruído
MIN_CONF = 0.10          # ignora deteções muito fracas (default)
MIN_AREA_FOOD = 1500.0   # ignora comida com área muito pequena (possível ruído)

# quando não há bbox: se duas áreas forem muito semelhantes, assume duplicado
AREA_SIMILARITY = 0.10   # 10% de diferença

# Dedup (quando há bbox): se IoU for alta, assume duplicado
IOU_THRESH = 0.85

# Faz dedup se as duas classes forem da MESMA família
DEDUP_FAMILIES = [
    {"rice", "pasta"},
    {"chips", "french fries"},
    {"steak", "grilled steak", "grilled chop"},
    {"meatballs", "minced meat", "stewed veal"},
    {"vegetables", "lettuce"},
]

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
    "chicken": 300.0,
}
DEFAULT_FULL_PLATE_GRAMS = 400.0

MIN_AREA_BY_CLASS = { #evita falsos positivos pequenos
}

def _min_area_for(name: str) -> float:
    return float(MIN_AREA_BY_CLASS.get(name, MIN_AREA_FOOD))

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


def _norm_label(name: Any) -> str:
    if not isinstance(name, str):
        return ""
    return name.strip()


def _min_conf_for(name: str) -> float:
    """Retorna o min confidence aplicável para esta classe (por defeito MIN_CONF)."""
    return float(MIN_CONF_BY_CLASS.get(name, MIN_CONF))


def _is_food_obj(obj: Dict[str, Any]) -> bool:
    """Só comida (para dedup e calorias). Plate/garbage/utensílios não entram aqui."""
    name = _norm_label(obj.get("label_name"))
    if not name or name in NON_FOOD:
        return False

    conf = _norm_conf(obj.get("confidence", 0.0))
    area = float(obj.get("area", 0.0) or 0.0)

    # aplica threshold por classe
    if conf < _min_conf_for(name):
        return False

    if area <= 0 or area < _min_area_for(name):
        return False

    return True


def _same_family(a: str, b: str) -> bool:
    """True se a e b estiverem na mesma família definida em DEDUP_FAMILIES."""
    for fam in DEDUP_FAMILIES:
        if a in fam and b in fam:
            return True
    return False


# Dedup helpers
def _iou_xyxy(a: List[float], b: List[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter

    return inter / union if union > 0 else 0.0


def _has_valid_bbox(obj: Dict[str, Any]) -> bool:
    bb = obj.get("bbox")
    return (
        isinstance(bb, list)
        and len(bb) == 4
        and all(isinstance(x, (int, float)) for x in bb)
    )


def _dedup_food_by_iou(objects: List[Dict[str, Any]], iou_thresh: float = IOU_THRESH) -> List[Dict[str, Any]]:
    """
    Dedup só para COMIDA usando bbox IoU.
    Agora é SELETIVO: só dedupa quando as classes são da mesma família.
    NÃO mexe em plate/garbage/utensílios.
    """
    food_with_bbox = [o for o in objects if _is_food_obj(o) and _has_valid_bbox(o)]
    if not food_with_bbox:
        return objects

    # Ordena por confidence (desc)
    food_with_bbox.sort(key=lambda o: _norm_conf(o.get("confidence", 0.0)), reverse=True)

    kept_food: List[Dict[str, Any]] = []
    for o in food_with_bbox:
        ok = True
        name_o = _norm_label(o.get("label_name"))

        for k in kept_food:
            name_k = _norm_label(k.get("label_name"))

            # Só dedup se forem da mesma família (ex: pasta vs rice)
            if not _same_family(name_o, name_k):
                continue

            iou = _iou_xyxy(o["bbox"], k["bbox"])
            if iou >= iou_thresh:
                print(
                    f"DEBUG DEDUP IOU(FAMILY): removed '{name_o}' (conf={_norm_conf(o.get('confidence')):.3f}) "
                    f"because it overlaps '{name_k}' (conf={_norm_conf(k.get('confidence')):.3f}) "
                    f"with IoU={iou:.3f}"
                )
                ok = False
                break

        if ok:
            kept_food.append(o)

    kept_ids = {id(o) for o in kept_food}

    final_list: List[Dict[str, Any]] = []
    for o in objects:
        # remove objetos que sejam comida + bbox e que não ficaram
        if _is_food_obj(o) and _has_valid_bbox(o):
            if id(o) in kept_ids:
                final_list.append(o)
        else:
            # plate/garbage/utensílios e qualquer coisa sem bbox passa sempre
            final_list.append(o)

    return final_list


def _dedup_food_by_similar_area(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fallback dedup: só para COMIDA, baseado em área semelhante.
    (Útil quando bbox não existe)
    """
    kept: List[Dict[str, Any]] = []

    for obj in objects:
        if not _is_food_obj(obj):
            kept.append(obj)
            continue

        area = float(obj.get("area", 0.0) or 0.0)
        conf = _norm_conf(obj.get("confidence", 0.0))

        merged = False
        for i, k in enumerate(kept):
            if not _is_food_obj(k):
                continue

            karea = float(k.get("area", 0.0) or 0.0)
            kconf = _norm_conf(k.get("confidence", 0.0))

            if karea > 0:
                similarity = min(area, karea) / max(area, karea)
                if similarity >= (1.0 - AREA_SIMILARITY):
                    if conf > kconf:
                        kept[i] = obj
                    merged = True
                    break

        if not merged:
            kept.append(obj)

    return kept


def _dedup_food(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    - Se houver bbox válida em comida -> dedup por IoU (melhor)
    - Senão -> fallback por área semelhante
    """
    has_any_food_bbox = any(_is_food_obj(o) and _has_valid_bbox(o) for o in objects)
    if has_any_food_bbox:
        return _dedup_food_by_iou(objects, iou_thresh=IOU_THRESH)
    return _dedup_food_by_similar_area(objects)


def estimate_calories_from_objects(
    objects: List[Dict[str, Any]],
    plate_area: float,
    garbage_area: float = 0.0,
    grams_per_plate: float = 500.0,  # usado como default
) -> Tuple[List[Dict[str, Any]], float]:

    kcal_base = load_kcal_base()  # kcal por 100g
    items: List[Dict[str, Any]] = []
    total = 0.0

    plate_usable = max(1.0, float(plate_area) - float(garbage_area))

    print("DEBUG BEFORE DEDUP:", [(o.get("label_name"), o.get("confidence"), o.get("area"), o.get("bbox")) for o in objects])
    objects = _dedup_food(objects)
    print("DEBUG AFTER DEDUP:", [(o.get("label_name"), o.get("confidence"), o.get("area"), o.get("bbox")) for o in objects])

    for obj in objects:
        name = _norm_label(obj.get("label_name"))
        conf = _norm_conf(obj.get("confidence", 0.0))
        area = float(obj.get("area", 0.0) or 0.0)

        # calorias só para comida
        if not name or name in NON_FOOD:
            continue

        # aplica threshold por classe
        if conf < _min_conf_for(name):
            continue

        if area < _min_area_for(name):
            continue

        # OVERRIDES têm prioridade sobre o CSV/JSON
        kcal_100g = OVERRIDES_KCAL_100G.get(name, kcal_base.get(name, 0.0))
        if kcal_100g <= 0 or area <= 0:
            continue

        # Porção (área relativa ao prato) + limites
        portion_ratio = area / plate_usable
        portion_ratio = max(0.0, min(MAX_PORTION, portion_ratio))

        # "Prato cheio" por alimento (ou fallback do parâmetro)
        fallback = float(grams_per_plate) if float(grams_per_plate) > 0 else DEFAULT_FULL_PLATE_GRAMS
        full_plate = FULL_PLATE_GRAMS.get(name, fallback)

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
