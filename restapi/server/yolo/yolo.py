from ultralytics import YOLO
import torch


class YOLOModel:
    def __init__(self):
        self.model = self.load_model()

    def load_model(self):
        try:
            print("Loading YOLO model...")
            model = YOLO("server/yolo/weights/yolov11-x-weights-v6.pt")
            print("Model loaded!")
            return model
        except Exception as e:
            print(f"Error loading model: {e}")
            return None

    def predict(self, frame):
        try:
            print("Predicting...")
            with torch.no_grad():
                results = self.model(frame, conf=0.15, iou=0.45, max_det=300)

            detected_objects = []

            for result in results:
                # Se não houver masks, evita rebentar
                if result.masks is None or result.masks.data is None:
                    # repetir só pelas boxes e calcular área pela bbox
                    for box in result.boxes:
                        cls_idx = int(box.cls.item())
                        conf = float(box.conf.item())

                        # xyxy como tensor shape (1,4)
                        bbox = [float(v) for v in box.xyxy[0].tolist()]
                        x1, y1, x2, y2 = bbox
                        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)

                        detected_objects.append({
                            "label": float(cls_idx),
                            "label_name": result.names[cls_idx],
                            "confidence": conf,
                            "bbox": bbox,   
                            "box": bbox,    
                            "area": float(area),
                        })
                    continue

                # masks + boxes
                for mask, box in zip(result.masks.data, result.boxes):
                    cls_idx = int(box.cls.item())
                    conf = float(box.conf.item())

                    bbox = [float(v) for v in box.xyxy[0].tolist()]  
                    area = float(mask.sum().item())

                    detected_objects.append({
                        "label": float(cls_idx),
                        "label_name": result.names[cls_idx],
                        "confidence": conf,
                        "bbox": bbox,   
                        "box": bbox,   
                        "area": area,
                    })

            print("Success!")
            return detected_objects, results

        except Exception as e:
            print(f"Error predicting: {e}")
            return None, None
