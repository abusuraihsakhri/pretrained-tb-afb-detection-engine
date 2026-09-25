import os
import cv2
import numpy as np
import torch
import json
import uuid
import subprocess
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydantic import BaseModel
import sys
import glob
import random
from fpdf import FPDF
from io import BytesIO
from typing import Any

try:
    from openslide.deepzoom import DeepZoomGenerator
except ImportError:
    DeepZoomGenerator = None

# Try to import YOLO if the ultralytics library is resolved
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

current_dir = Path(__file__).parent.resolve()
src_dir = current_dir.parent.parent / "02_CODE" / "src"
sys.path.append(str(src_dir))

app = FastAPI(title="Secure TB AFB API Backend")

static_dir = current_dir / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")

# 🛡️ SECURITY: Strict CORS baseline to prevent cross-origin medical data scraping
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8001", "http://localhost:8001"], 
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MAX_FILE_SIZE = 250 * 1024 * 1024 

class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
    label: int = 0

class InferenceResult(BaseModel):
    detections: list
    message: str
    grade: str
    hardware: str

# 🛡️ ARCHITECTURE: Global Hot-Swap Cache for Active Learning Weights
ACTIVE_MODEL = None
ACTIVE_MODEL_PATH = None
TRAINING_PROCESS = None

def run_tiled_inference(model, image, tile_size=640, overlap=64, conf_thresh=0.25):
    """
    Sliding-window tiled inference for full-slide microscope images.
    Splits image into tile_size patches, runs YOLO on each, 
    and maps all detections back to global image coordinates.
    """
    h, w = image.shape[:2]
    detections = []
    stride = tile_size - overlap

    for y0 in range(0, h, stride):
        for x0 in range(0, w, stride):
            x1 = min(x0 + tile_size, w)
            y1 = min(y0 + tile_size, h)
            tile = image[y0:y1, x0:x1]

            # Pad tile to tile_size x tile_size if near edge
            pad_h = tile_size - tile.shape[0]
            pad_w = tile_size - tile.shape[1]
            if pad_h > 0 or pad_w > 0:
                tile = cv2.copyMakeBorder(tile, 0, pad_h, 0, pad_w, cv2.BORDER_CONSTANT, value=0)

            results = model(tile, verbose=False)[0]
            if results.boxes is None:
                continue

            for box in results.boxes:
                conf = float(box.conf[0])
                if conf < conf_thresh:
                    continue
                cls = int(box.cls[0])
                # box.xywh is in tile coordinates — remap to global
                bx, by, bw, bh = box.xywh[0].tolist()
                global_cx = bx + x0
                global_cy = by + y0
                detections.append({
                    "bbox": [round(global_cx, 1), round(global_cy, 1), round(bw, 1), round(bh, 1)],
                    "confidence": round(conf, 2),
                    "class_id": cls,
                    "label": "AFB_Definite" if cls == 0 else "AFB_Possible"
                })

    return detections

def load_active_model(device='cpu'):
    """Monitors pinned checkpoint locations for newly trained YOLOv8 weights and hot-swaps them securely."""
    global ACTIVE_MODEL, ACTIVE_MODEL_PATH
    
    if not ULTRALYTICS_AVAILABLE:
        return None
        
    root_dir = current_dir.parent.parent
    # 🛡️ SECURITY REMEDIATION: Pinned candidate check avoids recursive rglob over entire 15,000+ file datalake
    candidate_paths = [
        root_dir / "03_MODELS" / "best.pt",
        root_dir / "best.pt",
    ]
    # Check latest training run weights if present
    runs_dir = root_dir / "runs" / "detect"
    if runs_dir.exists():
        run_weights = sorted(runs_dir.glob("*/weights/best.pt"), key=lambda p: p.stat().st_mtime, reverse=True)
        candidate_paths.extend(run_weights)
        
    valid_weights = [p for p in candidate_paths if p.is_file()]
    if not valid_weights:
        return None
        
    latest_path = str(valid_weights[0])
    
    # Execute the Hot-Swap if new weights are detected
    if latest_path != ACTIVE_MODEL_PATH:
        ACTIVE_MODEL_PATH = latest_path
        print(f"[ACTIVE LEARNING] 🚀 Hot-swapping to new Brain: {ACTIVE_MODEL_PATH}")
        ACTIVE_MODEL = YOLO(ACTIVE_MODEL_PATH)
        
    return ACTIVE_MODEL

def sanitize_pdf_text(text: Any) -> str:
    """Sanitize strings to latin-1 compatible characters for FPDF core fonts."""
    if text is None:
        return ""
    s = str(text).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("…", "...")
    return s.encode("latin-1", "replace").decode("latin-1")

@app.post("/api/v1/analyze", response_model=InferenceResult)
async def analyze_slide(request: Request, file: UploadFile = File(...)):
    """Research inference endpoint for ordinary raster microscopy images.

    Proprietary WSI formats are intentionally rejected here. They require
    OpenSlide-backed file handling rather than cv2.imdecode. This prevents an
    unreadable WSI from being misreported as a negative specimen.
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (250 MB limit).")

    filename = (file.filename or "").lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    if not any(filename.endswith(ext) for ext in allowed_exts):
        raise HTTPException(
            status_code=415,
            detail="This endpoint accepts raster microscopy images only. Use the OpenSlide/CLI workflow for WSI files.",
        )

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    yolo_model = load_active_model(device=device)
    if yolo_model is None:
        raise HTTPException(
            status_code=503,
            detail="No trained AFB checkpoint is installed. Add a validated best.pt before inference.",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (250 MB limit).")
    image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=415, detail="Image could not be decoded.")

    detections = run_tiled_inference(
        yolo_model, image, tile_size=640, overlap=64, conf_thresh=0.25
    )

    # Global NMS removes duplicate detections produced in overlapping tiles.
    if detections:
        boxes = []
        scores = []
        for det in detections:
            cx, cy, w, h = det["bbox"]
            boxes.append([int(cx - w / 2), int(cy - h / 2), int(w), int(h)])
            scores.append(float(det["confidence"]))
        keep = cv2.dnn.NMSBoxes(boxes, scores, 0.25, 0.45)
        keep_indices = set(np.asarray(keep).reshape(-1).tolist()) if len(keep) else set()
        detections = [d for i, d in enumerate(detections) if i in keep_indices]

    hardware = {
        "cuda": "NVIDIA CUDA",
        "mps": "Apple Metal/MPS",
        "cpu": "CPU",
    }.get(device.type, device.type)

    return InferenceResult(
        detections=detections,
        message="Research inference completed. No smear grade was inferred without an explicit field-sampling protocol.",
        grade="Not calculated",
        hardware=hardware,
    )

@app.post("/api/v1/save_annotation")
async def save_annotation(request: Request, file: UploadFile = File(...), boxes: str = Form(...)):
    if int(request.headers.get('content-length', 0)) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large.")
        
    try:
        boxes_list = json.loads(boxes)
        parsed_boxes = [BoundingBox(**b) for b in boxes_list]
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON injection attempt blocked.")
    
    # 🛡️ SECURITY REMEDIATION: Validate image binary decoding before saving to prevent corrupt/arbitrary file upload
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large.")
        
    image_array = np.frombuffer(contents, np.uint8)
    decoded_img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded_img is None or decoded_img.size == 0:
        raise HTTPException(status_code=415, detail="Corrupt or non-image binary uploaded.")

    base_name = uuid.uuid4().hex
    safe_img_name = f"{base_name}.jpg"
    safe_lbl_name = f"{base_name}.txt"
    
    # 🛡️ VALIDATION SPLIT: Randomized 20% logic for clinical data hygiene
    sub_folder = "val" if random.random() < 0.20 else "train"
    
    data_dir = current_dir.parent.parent / "01_DATA" / "processed_tiles" / sub_folder
    img_dir = data_dir / "images"
    lbl_dir = data_dir / "labels"
    
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    
    # Save Image bytes
    with open(img_dir / safe_img_name, "wb") as f:
        f.write(contents)
        
    # YOLO format extraction
    with open(lbl_dir / safe_lbl_name, "w", encoding="utf-8") as f:
        for b in parsed_boxes:
            f.write(f"{b.label} {b.x} {b.y} {b.width} {b.height}\n")
             
    return {
        "status": "success", 
        "message": f"Ingested {len(parsed_boxes)} ground-truth annotations into {sub_folder.upper()} set!"
    }

@app.post("/api/v1/trigger_training")
async def trigger_training():
    global TRAINING_PROCESS
    # 🛡️ SECURITY REMEDIATION: Prevent multiple concurrent background processes (Process Bombing / DoS)
    if TRAINING_PROCESS is not None and TRAINING_PROCESS.poll() is None:
        raise HTTPException(
            status_code=409, 
            detail="A training pipeline process is already active. Please wait for completion."
        )
        
    lbl_dir = current_dir.parent.parent / "01_DATA" / "processed_tiles" / "train" / "labels"
    if not lbl_dir.exists() or len(list(lbl_dir.glob("*.txt"))) == 0:
        raise HTTPException(status_code=400, detail="Cannot initiate Neural Engine: Zero annotated data vectors found.")
    
    train_script = current_dir.parent.parent / "02_CODE" / "scripts" / "02_train.py"
    if not train_script.is_file():
        raise HTTPException(status_code=500, detail="Training orchestrator script missing.")
        
    data_yaml = current_dir.parent.parent / "02_CODE" / "data.yaml"
    if not data_yaml.is_file():
        data_yaml = current_dir.parent.parent / "data.yaml"
        if not data_yaml.is_file():
            raise HTTPException(status_code=500, detail="data.yaml configuration missing.")

    TRAINING_PROCESS = subprocess.Popen([sys.executable, str(train_script), "--data", str(data_yaml)])
    return {"status": "success", "message": "Neural Training has been allocated."}

@app.post("/api/v1/render_payload")
async def render_payload(request: Request, file: UploadFile = File(...)):
    if int(request.headers.get('content-length', 0)) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. (250MB Hard Limit)")
        
    contents = await file.read()
    image_array = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    
    if image is None:
        raise HTTPException(status_code=415, detail="Backend CV2 Decoder failed to parse this specific Medical Binary structure. Ensure you upload supported patches (TIFF, JP2, JPG, PNG).")
        
    _, encoded_img = cv2.imencode('.jpg', image)
    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

@app.get("/api/v1/stats")
async def get_stats():
    # 🛡️ SECURITY: Safe enumeration of dataset to expose metrics without Arbitrary File Reads
    train_dir = current_dir.parent.parent / "01_DATA" / "processed_tiles" / "train"
    img_dir = train_dir / "images"
    lbl_dir = train_dir / "labels"
    
    valid_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    total_images = sum(1 for f in img_dir.iterdir() if f.suffix.lower() in valid_exts) if img_dir.exists() else 0
    total_annotations = 0
    
    if lbl_dir.exists():
        for txt_file in lbl_dir.glob("*.txt"):
            try:
                with open(txt_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            total_annotations += 1
            except OSError:
                continue
                
    has_weights = load_active_model() is not None
    
    return {
        "images_annotated": total_images,
        "afb_instances": total_annotations,
        "model_deployed": has_weights
    }

@app.post("/api/v1/export_report")
async def export_report(data: dict):
    # 🛡️ SECURITY: Structured PDF generation avoiding arbitrary HTML rendering and Unicode crashes
    pdf = FPDF()
    pdf.add_page()
    
    filename = sanitize_pdf_text(data.get('filename', 'Unknown'))
    grade = sanitize_pdf_text(data.get('grade', 'Pending'))
    hardware = sanitize_pdf_text(data.get('hardware', 'CPU'))
    pathologist_name = sanitize_pdf_text(data.get('pathologist_name', 'Not Specified'))
    count = int(data.get('count', 0))
    
    # Branded Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="TB PATHOLOGY INTELLIGENCE REPORT", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Report ID: {uuid.uuid4().hex[:8].upper()}", ln=True, align='C')
    pdf.ln(10)
    
    # Clinical Data
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="DIAGNOSTIC SUMMARY", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(200, 8, txt=f"Analysis Target: {filename}", ln=True)
    pdf.cell(200, 8, txt=f"WHO Grade: {grade}", ln=True)
    pdf.cell(200, 8, txt=f"AFB Detections Count: {count}", ln=True)
    pdf.cell(200, 8, txt=f"Hardware Backend: {hardware}", ln=True)
    pdf.cell(200, 8, txt=f"Reporting Pathologist: {pathologist_name}", ln=True)
    
    pdf.ln(20)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    # Medical Disclaimer
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(0, 5, txt="DISCLAIMER: This report is generated by an Artificial Intelligence system. It is intended for research and diagnostic assistance only and must be confirmed by a licensed professional before clinical action is taken.")
    
    pdf_output = pdf.output(dest='S')
    return Response(content=pdf_output, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=TB_AFB_Report.pdf"})

# 🛡️ GLOBAL CACHE FOR WSI TILES
WSI_HANDLES = {}

@app.get("/api/v1/wsi/tile/{wsi_id}/{z}/{x}/{y}")
async def get_wsi_tile(wsi_id: str, z: int, x: int, y: int):
    # Dynamic tile server for OpenSeadragon
    if not DeepZoomGenerator:
        raise HTTPException(status_code=501, detail="OpenSlide DeepZoom not available on this host.")
        
    # Security: Ensure WSI_ID is not a path injection
    # 🛡️ REMEDIATION: Force filename-only resolution and strict is_relative_to validation
    safe_wsi_id = Path(wsi_id).name
    base_data_dir = (current_dir.parent.parent / "01_DATA" / "raw_tiles").resolve()
    wsi_path = (base_data_dir / safe_wsi_id).resolve()
    
    # Final Jail Check: Resulting path MUST be within base_data_dir
    try:
        if not wsi_path.is_relative_to(base_data_dir):
            raise HTTPException(status_code=403, detail="Airtight Jail Breach Attempt Blocked.")
    except AttributeError:
        if os.path.commonpath([str(wsi_path), str(base_data_dir)]) != str(base_data_dir):
            raise HTTPException(status_code=403, detail="Airtight Jail Breach Attempt Blocked.")
    
    if wsi_id not in WSI_HANDLES:
        import openslide
        try:
            slide = openslide.OpenSlide(str(wsi_path))
            WSI_HANDLES[wsi_id] = DeepZoomGenerator(slide, tile_size=254, overlap=1, limit_bounds=False)
        except Exception:
            raise HTTPException(status_code=404, detail="WSI file not found or corrupted.")
            
    dz = WSI_HANDLES[wsi_id]
    try:
        tile = dz.get_tile(z, (x, y))
        buf = BytesIO()
        tile.save(buf, format='JPEG')
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Tile Coordinates.")
