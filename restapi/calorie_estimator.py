import json
import os
import sys
import logging
from typing import Dict, Any, List, Tuple, Optional

NON_FOOD = {
    "plate", "knife", "fork", "spoon", "bowl", "cup",
    "garbage", "board", "water", "coffee", "coffee cup", "water cup"
}

ALIAS_LABELS: Dict[str, str] = {
    # "meatballs": "stewed veal",
    # "minced meat": "stewed veal",
    # "veal": "chicken",
}

# Correções manuais para evitar valores absurdos do CSV
OVERRIDES_KCAL_100G = {
    "rice": 130.0,
    "strawberry": 32.0,
    "vegetables": 35.0,
    "soup": 60.0,
    "chicken": 190.0,  
}

# Cortar falsos positivos por classe (confidence mínima)
MIN_CONF_BY_CLASS = {
    "pasta": 0.15,
    "soup": 0.25,
}

# Cortar falsos positivos por classe (área mínima)
MIN_AREA_FOOD = 1500.0
MIN_AREA_BY_CLASS = {
    "pasta": 20000.0,
}

def _min_area_for(name: str) -> float:
    return float(MIN_AREA_BY_CLASS.get(name, MIN_AREA_FOOD))

# Limites de sanidade (calorias)
MAX_PORTION = 0.70       # máximo 70% do prato por label (após normalização)
MAX_GRAMS_ITEM = 350.0
MIN_GRAMS_ITEM = 10.0
MIN_CONF = 0.10

# quando não há bbox: se duas áreas forem muito semelhantes, assume duplicado
AREA_SIMILARITY = 0.10

# Dedup (quando há bbox): se IoU for alta, assume duplicado
IOU_THRESH = 0.85

# Dedup por família
DEDUP_FAMILIES = [
    {"rice", "pasta"},
    {"chips", "french fries"},
    {"steak", "grilled steak", "grilled chop"},
    {"meatballs", "minced meat", "stewed veal"},
    {"vegetables", "lettuce"},
]

# MUTEX: classes que o YOLO confunde na MESMA zona
MUTEX_GROUPS = [
    {"pasta", "soup"},
    {"rice", "soup"},
]
MUTEX_IOU_THRESH = 0.95

# Preferências quando há conflito mutex (maior = ganha)
CLASS_PRIORITY = {
    "pasta": 3,
    "rice": 3,
    "soup": 1,
}

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

# ---------------- Logging ----------------
logger = logging.getLogger("calorie_estimator")

def _setup_logging() -> None:
    """
    Controla logs via env var:
      DEBUG=true/1/on/yes -> DEBUG
      caso contrário -> INFO
    """
    dbg = os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    level = logging.DEBUG if dbg else logging.INFO

    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)

_setup_logging()

# ---------------- Cache do calorie_map.json ----------------
_KCAL_BASE_CACHE: Optional[Dict[str, float]] = None

def load_kcal_base() -> Dict[str, float]:
    here = os.path.dirname(__file__)
    path = os.path.join(here, "calorie_map.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: float(v) for k, v in data.items()}

def get_kcal_base() -> Dict[str, float]:
    """Lê o calorie_map.json apenas 1 vez por processo (cache em memória)."""
    global _KCAL_BASE_CACHE
    if _KCAL_BASE_CACHE is None:
        logger.debug("Loading calorie_map.json (cache miss)")
        _KCAL_BASE_CACHE = load_kcal_base()
    return _KCAL_BASE_CACHE


# ---------------- Normalizações ----------------
def _norm_conf(conf: Any) -> float:
    try:
        c = float(conf)
    except Exception:
        return 0.0
    if c > 1.0:
        c /= 100.0
    return max(0.0, min(1.0, c))

def _norm_label(name: Any) -> str:
    return name.strip() if isinstance(name, str) else ""

def _alias_label(name: str) -> str:
    return ALIAS_LABELS.get(name, name)

def _min_conf_for(name: str) -> float:
    return float(MIN_CONF_BY_CLASS.get(name, MIN_CONF))


# ---------------- BBOX helpers (Opção B: union area) ----------------
def _has_valid_bbox(obj: Dict[str, Any]) -> bool:
    bb = obj.get("bbox")
    return (
        isinstance(bb, list)
        and len(bb) == 4
        and all(isinstance(x, (int, float)) for x in bb)
    )

def _bbox_area(bb: List[float]) -> float:
    x1, y1, x2, y2 = bb
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)

def _bbox_intersection(a: List[float], b: List[float]) -> Optional[List[float]]:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]

def _union_area_rects(rects: List[List[float]]) -> float:
    """
    Área da união de retângulos [x1,y1,x2,y2] (sem double-counting).
    Sweep-line em X + merge de intervalos em Y.
    """
    if not rects:
        return 0.0

    xs = sorted(set([r[0] for r in rects] + [r[2] for r in rects]))
    area = 0.0

    for i in range(len(xs) - 1):
        x_left, x_right = xs[i], xs[i + 1]
        if x_right <= x_left:
            continue

        strip_width = x_right - x_left
        intervals: List[List[float]] = []

        for x1, y1, x2, y2 in rects:
            # retângulos que cobrem totalmente este strip em X
            if x1 <= x_left and x2 >= x_right:
                intervals.append([y1, y2])

        if not intervals:
            continue

        intervals.sort(key=lambda t: t[0])

        covered_y = 0.0
        cur_s, cur_e = intervals[0]
        for s, e in intervals[1:]:
            if s <= cur_e:
                cur_e = max(cur_e, e)
            else:
                covered_y += max(0.0, cur_e - cur_s)
                cur_s, cur_e = s, e
        covered_y += max(0.0, cur_e - cur_s)

        area += strip_width * covered_y

    return float(area)

def _get_plate_bbox(objects: List[Dict[str, Any]]) -> Optional[List[float]]:
    plates = [
        o for o in objects
        if _norm_label(o.get("label_name")) == "plate" and _has_valid_bbox(o)
    ]
    if not plates:
        return None
    plates.sort(key=lambda o: _bbox_area(o["bbox"]), reverse=True)
    return plates[0]["bbox"]

def compute_food_area_union(objects: List[Dict[str, Any]], crop_to_plate: bool = True) -> float:
    """
    FoodArea (Opção B):
    - usa união das bbox de comida para não somar overlaps duas vezes
    - opcional: recorta cada bbox ao bbox do prato (recomendado)
    """
    plate_bb = _get_plate_bbox(objects) if crop_to_plate else None
    if crop_to_plate and plate_bb is None:
        logger.debug("compute_food_area_union: no plate bbox -> 0")
        return 0.0

    rects: List[List[float]] = []
    for o in objects:
        if not _is_food_obj(o) or not _has_valid_bbox(o):
            continue

        bb = o["bbox"]
        if plate_bb is not None:
            bb = _bbox_intersection(bb, plate_bb)
            if bb is None:
                continue

        if _bbox_area(bb) <= 0:
            continue

        rects.append(bb)

    union = _union_area_rects(rects)
    logger.debug("compute_food_area_union: rects=%d union=%.2f", len(rects), union)
    return union


# Regras de comida 
def _is_food_obj(obj: Dict[str, Any]) -> bool:
    """Só comida (para dedup e calorias)."""
    name = _alias_label(_norm_label(obj.get("label_name")))
    if not name or name in NON_FOOD:
        return False

    conf = _norm_conf(obj.get("confidence", 0.0))
    area = float(obj.get("area", 0.0) or 0.0)

    if conf < _min_conf_for(name):
        return False
    if area <= 0 or area < _min_area_for(name):
        return False

    return True

def _same_family(a: str, b: str) -> bool:
    # mesma label também conta como “família” para dedup
    if a == b:
        return True
    for fam in DEDUP_FAMILIES:
        if a in fam and b in fam:
            return True
    return False

def _same_mutex(a: str, b: str) -> bool:
    for g in MUTEX_GROUPS:
        if a in g and b in g:
            return True
    return False


# Dedup (IoU) 
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

def _dedup_food_by_iou(objects: List[Dict[str, Any]], iou_thresh: float = IOU_THRESH) -> List[Dict[str, Any]]:
    """
    Dedup só para COMIDA usando bbox IoU.
    - FAMILY (inclui mesma label): dedup se IoU >= IOU_THRESH, fica a melhor.
    - MUTEX: se bbox quase igual (IoU >= MUTEX_IOU_THRESH), escolhe por prioridade e depois confidence.
    """
    food_with_bbox = [o for o in objects if _is_food_obj(o) and _has_valid_bbox(o)]
    if not food_with_bbox:
        return objects

    food_with_bbox.sort(key=lambda o: _norm_conf(o.get("confidence", 0.0)), reverse=True)
    kept_food: List[Dict[str, Any]] = []

    for o in food_with_bbox:
        name_o = _alias_label(_norm_label(o.get("label_name")))
        conf_o = _norm_conf(o.get("confidence", 0.0))
        ok = True

        for k in list(kept_food):
            name_k = _alias_label(_norm_label(k.get("label_name")))
            conf_k = _norm_conf(k.get("confidence", 0.0))

            is_family = _same_family(name_o, name_k)
            is_mutex = _same_mutex(name_o, name_k)
            if not (is_family or is_mutex):
                continue

            iou = _iou_xyxy(o["bbox"], k["bbox"])

            # MUTEX
            if is_mutex and iou >= MUTEX_IOU_THRESH:
                pr_o = CLASS_PRIORITY.get(name_o, 0)
                pr_k = CLASS_PRIORITY.get(name_k, 0)

                if pr_o < pr_k:
                    ok = False
                    break

                if pr_o > pr_k:
                    logger.debug("DEDUP MUTEX: removed '%s' kept '%s' (IoU=%.3f)", name_k, name_o, iou)
                    kept_food.remove(k)
                    continue

                if conf_o <= conf_k:
                    ok = False
                    break

                logger.debug("DEDUP MUTEX: removed '%s' kept '%s' (IoU=%.3f)", name_k, name_o, iou)
                kept_food.remove(k)
                continue

            # FAMILY (inclui mesma label)
            if is_family and iou >= iou_thresh:
                logger.debug(
                    "DEDUP FAMILY: removed '%s' (conf=%.3f) because overlaps '%s' (conf=%.3f) IoU=%.3f",
                    name_o, conf_o, name_k, conf_k, iou
                )
                ok = False
                break

        if ok:
            kept_food.append(o)

    kept_ids = {id(o) for o in kept_food}

    final_list: List[Dict[str, Any]] = []
    for o in objects:
        if _is_food_obj(o) and _has_valid_bbox(o):
            if id(o) in kept_ids:
                final_list.append(o)
        else:
            final_list.append(o)

    return final_list

def _dedup_food_by_similar_area(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    has_any_food_bbox = any(_is_food_obj(o) and _has_valid_bbox(o) for o in objects)
    if has_any_food_bbox:
        return _dedup_food_by_iou(objects, iou_thresh=IOU_THRESH)
    return _dedup_food_by_similar_area(objects)


# ---------------- Agregação e calorias ----------------
def _aggregate_by_label(objects: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    Junta múltiplas deteções do mesmo label:
      - soma de area
      - confidence: guarda a maior (só para reporting)
      - count: nº de boxes agregadas
    """
    agg: Dict[str, Dict[str, float]] = {}
    for o in objects:
        name = _alias_label(_norm_label(o.get("label_name")))
        if not name or name in NON_FOOD:
            continue

        conf = _norm_conf(o.get("confidence", 0.0))
        area = float(o.get("area", 0.0) or 0.0)

        if conf < _min_conf_for(name):
            continue
        if area < _min_area_for(name):
            continue

        if name not in agg:
            agg[name] = {"area": 0.0, "conf": 0.0, "count": 0.0}
        agg[name]["area"] += area
        agg[name]["conf"] = max(agg[name]["conf"], conf)
        agg[name]["count"] += 1.0

    return agg

def estimate_calories_from_objects(
    objects: List[Dict[str, Any]],
    plate_area: float,
    garbage_area: float = 0.0,
    grams_per_plate: float = 500.0,
) -> Tuple[List[Dict[str, Any]], float]:

    kcal_base = get_kcal_base()
    items: List[Dict[str, Any]] = []
    total = 0.0

    plate_usable = max(1.0, float(plate_area) - float(garbage_area))

    logger.debug("BEFORE DEDUP labels=%s", [o.get("label_name") for o in objects])
    objects = _dedup_food(objects)
    logger.debug("AFTER DEDUP labels=%s", [o.get("label_name") for o in objects])

    agg = _aggregate_by_label(objects)
    if not agg:
        return [], 0.0

    # porções cruas SEM cap e normaliza se somar > 1
    raw_portions: Dict[str, float] = {}
    for name, info in agg.items():
        area_sum = float(info["area"])
        raw = max(0.0, area_sum / plate_usable)
        raw_portions[name] = raw

    sum_raw = sum(raw_portions.values())
    scale = (1.0 / sum_raw) if sum_raw > 1.0 else 1.0
    logger.debug("portion sum_raw=%.3f scale=%.3f", sum_raw, scale)

    fallback = float(grams_per_plate) if float(grams_per_plate) > 0 else DEFAULT_FULL_PLATE_GRAMS

    for name, raw in raw_portions.items():
        portion_ratio = raw * scale
        portion_ratio = max(0.0, min(MAX_PORTION, portion_ratio))

        full_plate = FULL_PLATE_GRAMS.get(name, fallback)
        grams_est = portion_ratio * full_plate
        grams_est = max(MIN_GRAMS_ITEM, min(MAX_GRAMS_ITEM, grams_est))

        kcal_100g = OVERRIDES_KCAL_100G.get(name, kcal_base.get(name, 0.0))
        if kcal_100g <= 0:
            continue

        kcal_raw = (kcal_100g / 100.0) * grams_est
        kcal_final = round(kcal_raw, 2)

        items.append({
            "label_name": name,
            "confidence": round(float(agg[name]["conf"]), 4),
            "count": int(agg[name]["count"]),
            "area": round(float(agg[name]["area"]), 2),
            "portion_ratio": round(portion_ratio, 4),
            "grams_est": round(grams_est, 1),
            "kcal_per_100g": round(float(kcal_100g), 2),
            "kcal_estimated": kcal_final,
            "formula": "(kcal_100g/100)*grams_est"
        })
        total += kcal_final

    items.sort(key=lambda x: float(x.get("kcal_estimated", 0.0)), reverse=True)
    return items, round(total, 2)
