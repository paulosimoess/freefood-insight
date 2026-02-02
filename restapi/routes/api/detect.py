from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from server.yolo.yolo import YOLOModel
from PIL import Image
import io
import base64

from calorie_estimator import (
    estimate_calories_from_objects,
    compute_food_area_union,
)

router = APIRouter()
yolo_model = YOLOModel()


def pil_to_base64_jpeg(img: Image.Image, quality: int = 90) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def generate_detection_image(result) -> Image.Image:
    # imagem com boxes/labels (deteções normais)
    arr = result.plot()  # default: boxes=True
    return Image.fromarray(arr)


def generate_clustering_image(result) -> Image.Image:
    # “clustering” (sem boxes, só labels/cores por classe)
    arr = result.plot(boxes=False, labels=True, color_mode="class")
    return Image.fromarray(arr)


# helpers desperdicio
def _bbox_area(bb) -> float:
    x1, y1, x2, y2 = bb
    return max(0.0, float(x2) - float(x1)) * max(0.0, float(y2) - float(y1))


def _clip_bbox(bb, clip_bb):
    x1, y1, x2, y2 = map(float, bb)
    cx1, cy1, cx2, cy2 = map(float, clip_bb)
    nx1, ny1 = max(x1, cx1), max(y1, cy1)
    nx2, ny2 = min(x2, cx2), min(y2, cy2)
    if nx2 <= nx1 or ny2 <= ny1:
        return None
    return [nx1, ny1, nx2, ny2]


def _union_area(rects) -> float:
    """
    Área da união de retângulos axis-aligned (bboxes).
    Algoritmo por varrimento em x (suficiente para o teu caso).
    """
    if not rects:
        return 0.0

    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    total = 0.0

    for i in range(len(xs) - 1):
        x_left, x_right = xs[i], xs[i + 1]
        if x_right <= x_left:
            continue

        ys = []
        for x1, y1, x2, y2 in rects:
            if x1 <= x_left and x2 >= x_right:
                ys.append((y1, y2))

        if not ys:
            continue

        ys.sort()
        cur_s, cur_e = ys[0]
        merged = 0.0

        for s, e in ys[1:]:
            if s <= cur_e:
                cur_e = max(cur_e, e)
            else:
                merged += max(0.0, cur_e - cur_s)
                cur_s, cur_e = s, e

        merged += max(0.0, cur_e - cur_s)
        total += (x_right - x_left) * merged

    return float(total)


def build_response(detected_objects, results):
    # Base64 (sem escrever ficheiros temporários)
    det_img = generate_detection_image(results[0])
    clustering_img = generate_clustering_image(results[0])

    base64_image = pil_to_base64_jpeg(det_img)
    base64_clustering_image = pil_to_base64_jpeg(clustering_img)

    garbage_classes = {35.0}
    ignore_classes = {58.0, 31.0, 42.0, 70.0, 83.0, 25.0, 27.0, 22.0, 11.0, 8.0}

    plate_bbox = None
    plate_bbox_area = 0.0

    for obj in detected_objects:
        if obj.get("label") == 58.0 and obj.get("bbox"):
            a = _bbox_area(obj["bbox"])
            if a > plate_bbox_area:
                plate_bbox_area = a
                plate_bbox = obj["bbox"]

    if not plate_bbox or plate_bbox_area <= 0:
        return JSONResponse(content={"error": "No plate detected in the image"}, status_code=400)

    food_area = float(compute_food_area_union(detected_objects, crop_to_plate=True))

    # garbage_area por união de bbox (crop ao prato)
    garbage_rects = []
    for obj in detected_objects:
        bb = obj.get("bbox")
        if not bb:
            continue
        lab = obj.get("label")
        if lab in garbage_classes:
            bb2 = _clip_bbox(bb, plate_bbox)
            if bb2:
                garbage_rects.append(bb2)

    garbage_area = float(_union_area(garbage_rects))

    plate_area = float(plate_bbox_area)
    denom = max(1.0, plate_area - garbage_area)
    waste_percentage = (food_area / denom) * 100.0
    waste_percentage = min(max(waste_percentage, 0.0), 100.0)

    return {
        "objects": detected_objects,
        "image_base64": base64_image,
        "clustering_image_base64": base64_clustering_image,
        "waste_percentage": waste_percentage,
        "food_area": food_area,
        "garbage_area": garbage_area,
        "plate_area": plate_area,
        "food_area_method": "bbox_union_crop_to_plate",
        "waste_debug": {
            "plate_bbox_area": plate_area,
            "food_union_area": food_area,
            "garbage_union_area": garbage_area,
            "denom": denom,
        },
    }


@router.post("/detect")
async def detect_objects(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    detected_objects, results = yolo_model.predict(image)
    if detected_objects is None or results is None:
        return JSONResponse(content={"error": "Error in object detection"}, status_code=500)

    payload = build_response(detected_objects, results)
    if isinstance(payload, JSONResponse):
        return payload

    return JSONResponse(content=payload)


@router.post("/calories")
async def detect_calories(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    detected_objects, results = yolo_model.predict(image)
    if detected_objects is None or results is None:
        return JSONResponse(content={"error": "Error in object detection"}, status_code=500)

    print("DEBUG YOLO detected_objects:")
    for o in detected_objects:
        print({
            "label_name": o.get("label_name"),
            "confidence": o.get("confidence"),
            "area": o.get("area"),
            "label": o.get("label"),
            "bbox": o.get("bbox"),
        })

    payload = build_response(detected_objects, results)
    if isinstance(payload, JSONResponse):
        return payload

    cal_items, cal_total = estimate_calories_from_objects(
        detected_objects,
        plate_area=payload["plate_area"],       
        garbage_area=payload["garbage_area"],   # bbox union area
        grams_per_plate=500.0,
    )

    payload["calories"] = {
        "items": cal_items,
        "total": cal_total,
        "formula": "(kcal_100g/100)*grams_est"
    }

    return JSONResponse(content=payload)
