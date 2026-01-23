from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from server.yolo.yolo import YOLOModel
from PIL import Image
import io
import base64

from calorie_estimator import estimate_calories_from_objects

router = APIRouter()
yolo_model = YOLOModel()


def generate_clustering_image(result):
    clustering_image_array = result.plot(boxes=False, labels=True, color_mode="class")
    clustering_image = Image.fromarray(clustering_image_array)
    return clustering_image


def build_response(detected_objects, results):
    # Save temporary image with detections
    output_image_path = "output_image.jpg"
    results[0].save(output_image_path)

    # Save temporary clustering image
    clustering_image_path = "clustering_image.jpg"
    clustering_image = generate_clustering_image(results[0])
    clustering_image.save(clustering_image_path)

    # Convert images to base64
    with open(output_image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")

    with open(clustering_image_path, "rb") as image_file:
        base64_clustering_image = base64.b64encode(image_file.read()).decode("utf-8")

    # Calculate waste percentage
    garbage_classes = {35.0}
    ignore_classes = {58.0, 31.0, 42.0, 70.0, 83.0, 25.0, 27.0, 22.0, 11.0, 8.0}
    plate_area = 0
    garbage_area = 0
    food_area = 0

    for obj in detected_objects:
        if obj["label"] == 58.0:
            plate_area += obj["area"]

        if obj["label"] in garbage_classes:
            garbage_area += obj["area"]

        if obj["label"] not in garbage_classes and obj["label"] not in ignore_classes:
            food_area += obj["area"]

    if plate_area == 0:
        return JSONResponse(
            content={"error": "No plate detected in the image"}, status_code=400
        )

    if plate_area > garbage_area:
        waste_percentage = (food_area / (plate_area - garbage_area)) * 100
    else:
        waste_percentage = 0

    waste_percentage = min(max(waste_percentage, 0), 100)

    return {
        "objects": detected_objects,
        "image_base64": base64_image,
        "clustering_image_base64": base64_clustering_image,
        "waste_percentage": waste_percentage,
        "food_area": food_area,
        "garbage_area": garbage_area,
        "plate_area": plate_area,
    }


@router.post("/detect")
async def detect_objects(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    detected_objects, results = yolo_model.predict(image)

    if results is None:
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

    if results is None:
        return JSONResponse(content={"error": "Error in object detection"}, status_code=500)

    payload = build_response(detected_objects, results)
    if isinstance(payload, JSONResponse):
        return payload

    cal_items, cal_total = estimate_calories_from_objects(detected_objects)
    payload["calories"] = {
        "items": cal_items,
        "total": cal_total,
        "formula": "kcal_base * confidence",
    }

    return JSONResponse(content=payload)
