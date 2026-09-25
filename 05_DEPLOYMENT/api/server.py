import os
import hashlib
import secrets
import cv2
import numpy as np
import json
import uuid
import subprocess
from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, Request, Form, Header
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydantic import BaseModel, Field, model_validator
import sys
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from io import BytesIO
from typing import Any, Literal
from collections import OrderedDict

try:
    from openslide.deepzoom import DeepZoomGenerator
except ImportError:
    DeepZoomGenerator = None

try:
    import torch
except ImportError:
    torch = None

# Try to import YOLO if the ultralytics library is resolved
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

current_dir = Path(__file__).parent.resolve()
src_dir = current_dir.parent.parent / "02_CODE" / "src"
sys.path.append(str(src_dir))

app = FastAPI(
    title="TB-AFB Research API",
    description="Research-use object detection API. Not validated for diagnosis.",
)

static_dir = current_dir / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8001", "http://localhost:8001"], 
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def prevent_api_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

MAX_FILE_SIZE = int(os.getenv("TB_AFB_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("TB_AFB_MAX_IMAGE_PIXELS", "100000000"))
MAX_ANNOTATIONS = int(os.getenv("TB_AFB_MAX_ANNOTATIONS", "10000"))
API_TOKEN = os.getenv("TB_AFB_API_TOKEN")
ALLOW_REMOTE_TRAINING = os.getenv("TB_AFB_ALLOW_REMOTE_TRAINING") == "1"
EXPECTED_MODEL_SHA256 = os.getenv("TB_AFB_MODEL_SHA256")


def require_acceptable_content_length(request: Request) -> None:
    value = request.headers.get("content-length")
    if value is None:
        return
    try:
        declared_size = int(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from exc
    if declared_size < 0:
        raise HTTPException(status_code=400, detail="Invalid Content-Length header.")
    if declared_size > MAX_FILE_SIZE:
        limit_mib = MAX_FILE_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the configured {limit_mib:g} MiB limit.",
        )

class BoundingBox(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)
    label: Literal[0] = 0

    @model_validator(mode="after")
    def box_within_image(self):
        if (
            self.x - self.width / 2 < 0
            or self.y - self.height / 2 < 0
            or self.x + self.width / 2 > 1
            or self.y + self.height / 2 > 1
        ):
            raise ValueError("Bounding box extends outside normalized image bounds.")
        return self

class InferenceResult(BaseModel):
    detections: list
    message: str
    grade: str
    hardware: str


class ResearchReportRequest(BaseModel):
    filename: str = Field(default="Unknown", max_length=200)
    grade: str = Field(default="Not calculated", max_length=100)
    hardware: str = Field(default="Unknown", max_length=100)
    reviewer_name: str = Field(default="Not specified", max_length=100)
    count: int = Field(default=0, ge=0, le=1_000_000)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Require an API key whenever the deployment configures one."""
    if API_TOKEN and (
        x_api_key is None or not secrets.compare_digest(x_api_key, API_TOKEN)
    ):
        raise HTTPException(status_code=401, detail="Valid X-API-Key required.")


def require_mutation_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Disable data-changing endpoints unless an explicit token is configured."""
    if not API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Mutation endpoints are disabled until TB_AFB_API_TOKEN is configured.",
        )
    if x_api_key is None or not secrets.compare_digest(x_api_key, API_TOKEN):
        raise HTTPException(status_code=401, detail="Valid X-API-Key required.")

# 🛡️ ARCHITECTURE: Global Hot-Swap Cache for Active Learning Weights
ACTIVE_MODEL = None
ACTIVE_MODEL_PATH = None
TRAINING_PROCESS = None


@app.get("/healthz", include_in_schema=False)
async def healthcheck():
    checkpoint_status = local_checkpoint_status()
    return {
        "status": "ok",
        "mode": "research_only",
        "checkpoint_status": checkpoint_status,
        "model_ready": checkpoint_status == "verified",
    }

def run_tiled_inference(model, image, tile_size=640, overlap=64, conf_thresh=0.25):
    """
    Sliding-window tiled inference for full-slide microscope images.
    Splits image into tile_size patches, runs YOLO on each, 
    and maps all detections back to global image coordinates.
    """
    h, w = image.shape[:2]
    detections = []
    if overlap < 0 or overlap >= tile_size:
        raise ValueError("overlap must be non-negative and smaller than tile_size")
    stride = tile_size - overlap

    def positions(length):
        if length <= tile_size:
            return [0]
        values = list(range(0, length - tile_size + 1, stride))
        final = length - tile_size
        if values[-1] != final:
            values.append(final)
        return values

    for y0 in positions(h):
        for x0 in positions(w):
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
                    "label": "AFB_candidate"
                })

    return detections

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_checkpoint_status() -> str:
    """Return a non-sensitive checkpoint integrity state for health checks."""
    root_dir = current_dir.parent.parent.resolve()
    model_dir = (root_dir / "03_MODELS").resolve()
    configured = Path(
        os.getenv("TB_AFB_MODEL_PATH", str(model_dir / "best.pt"))
    ).resolve()
    if not configured.is_relative_to(model_dir):
        return "invalid_path"
    if not configured.is_file():
        return "missing"
    expected_hash = EXPECTED_MODEL_SHA256
    checksum_file = model_dir / f"{configured.name}.sha256"
    if expected_hash is None and checksum_file.is_file():
        parts = checksum_file.read_text(encoding="utf-8").split()
        expected_hash = parts[0] if parts else None
    if not expected_hash:
        return "unpinned"
    return (
        "verified"
        if secrets.compare_digest(file_sha256(configured).lower(), expected_hash.lower())
        else "hash_mismatch"
    )


def load_active_model(device='cpu'):
    """Load only the explicitly pinned local checkpoint."""
    global ACTIVE_MODEL, ACTIVE_MODEL_PATH
    
    if not ULTRALYTICS_AVAILABLE:
        return None
        
    root_dir = current_dir.parent.parent.resolve()
    model_dir = (root_dir / "03_MODELS").resolve()
    configured = Path(os.getenv("TB_AFB_MODEL_PATH", str(model_dir / "best.pt"))).resolve()
    if not configured.is_relative_to(model_dir):
        raise RuntimeError("TB_AFB_MODEL_PATH must remain inside 03_MODELS.")
    if not configured.is_file():
        return None

    digest = file_sha256(configured)
    expected_hash = EXPECTED_MODEL_SHA256
    checksum_file = model_dir / f"{configured.name}.sha256"
    if expected_hash is None and checksum_file.is_file():
        parts = checksum_file.read_text(encoding="utf-8").split()
        expected_hash = parts[0] if parts else None
    if not expected_hash:
        raise RuntimeError("Pinned checkpoint SHA-256 is required before inference.")
    if not secrets.compare_digest(digest.lower(), expected_hash.lower()):
        raise RuntimeError("Pinned checkpoint SHA-256 verification failed.")

    identity = f"{configured}:{digest}"
    if identity != ACTIVE_MODEL_PATH:
        ACTIVE_MODEL_PATH = identity
        print(f"Loading pinned research checkpoint: {configured.name} ({digest[:12]}...)")
        ACTIVE_MODEL = YOLO(str(configured))
        if hasattr(ACTIVE_MODEL, "to"):
            ACTIVE_MODEL.to(str(device))
        
    return ACTIVE_MODEL

def sanitize_pdf_text(text: Any) -> str:
    """Sanitize strings to latin-1 compatible characters for FPDF core fonts."""
    if text is None:
        return ""
    s = str(text).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("…", "...")
    return s.encode("latin-1", "replace").decode("latin-1")

@app.post("/api/v1/analyze", response_model=InferenceResult)
async def analyze_slide(
    request: Request,
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
):
    """Research inference endpoint for ordinary raster microscopy images.

    Proprietary WSI formats are intentionally rejected here. They require
    OpenSlide-backed file handling rather than cv2.imdecode. This prevents an
    unreadable WSI from being misreported as a negative specimen.
    """
    require_acceptable_content_length(request)

    filename = (file.filename or "").lower()
    allowed_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    if not any(filename.endswith(ext) for ext in allowed_exts):
        raise HTTPException(
            status_code=415,
            detail="This endpoint accepts raster microscopy images only. Use the OpenSlide/CLI workflow for WSI files.",
        )

    if torch is not None and torch.cuda.is_available():
        device = "cuda"
    elif (
        torch is not None
        and hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
    ):
        device = "mps"
    else:
        device = "cpu"

    yolo_model = load_active_model(device=device)
    if yolo_model is None:
        raise HTTPException(
            status_code=503,
            detail="No trained AFB checkpoint is installed. Add a validated best.pt before inference.",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit.")
    image = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=415, detail="Image could not be decoded.")
    if image.shape[0] * image.shape[1] > MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=413,
            detail="Decoded image dimensions exceed the configured pixel limit.",
        )

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
    }.get(device, device)

    return InferenceResult(
        detections=detections,
        message="Research inference completed. No smear grade was inferred without an explicit field-sampling protocol.",
        grade="Not calculated",
        hardware=hardware,
    )

@app.post("/api/v1/save_annotation")
async def save_annotation(
    request: Request,
    file: UploadFile = File(...),
    boxes: str = Form(...),
    _: None = Depends(require_mutation_key),
):
    require_acceptable_content_length(request)
        
    try:
        boxes_list = json.loads(boxes)
        if not isinstance(boxes_list, list):
            raise ValueError("boxes must be a JSON array")
        if len(boxes_list) > MAX_ANNOTATIONS:
            raise ValueError(f"annotation limit is {MAX_ANNOTATIONS}")
        parsed_boxes = [BoundingBox(**b) for b in boxes_list]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid annotation payload: {exc}")
    
    # 🛡️ SECURITY REMEDIATION: Validate image binary decoding before saving to prevent corrupt/arbitrary file upload
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large.")
        
    image_array = np.frombuffer(contents, np.uint8)
    decoded_img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded_img is None or decoded_img.size == 0:
        raise HTTPException(status_code=415, detail="Corrupt or non-image binary uploaded.")
    if decoded_img.shape[0] * decoded_img.shape[1] > MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=413,
            detail="Decoded image dimensions exceed the configured pixel limit.",
        )

    base_name = uuid.uuid4().hex
    safe_img_name = f"{base_name}.png"
    safe_lbl_name = f"{base_name}.txt"

    # Submitted annotations enter a review queue. They are never assigned to a
    # split automatically because the patient/slide grouping is unknown here.
    data_dir = current_dir.parent.parent / "01_DATA" / "review_queue"
    img_dir = data_dir / "images"
    lbl_dir = data_dir / "labels"
    
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    
    encoded_ok, encoded_image = cv2.imencode(".png", decoded_img)
    if not encoded_ok:
        raise HTTPException(status_code=500, detail="Image could not be normalized for storage.")
    with open(img_dir / safe_img_name, "wb") as f:
        f.write(encoded_image.tobytes())
        
    # YOLO format extraction
    with open(lbl_dir / safe_lbl_name, "w", encoding="utf-8") as f:
        for b in parsed_boxes:
            f.write(f"{b.label} {b.x} {b.y} {b.width} {b.height}\n")
             
    return {
        "status": "queued",
        "record_id": base_name,
        "message": (
            f"Queued {len(parsed_boxes)} annotations for provenance review and "
            "group-aware split assignment."
        ),
    }

@app.post("/api/v1/trigger_training")
async def trigger_training(_: None = Depends(require_mutation_key)):
    global TRAINING_PROCESS
    if not ALLOW_REMOTE_TRAINING:
        raise HTTPException(
            status_code=403,
            detail="Remote training is disabled. Set TB_AFB_ALLOW_REMOTE_TRAINING=1 explicitly.",
        )
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
    return {"status": "started", "message": "Research training preflight started."}

@app.post("/api/v1/render_payload")
async def render_payload(
    request: Request,
    file: UploadFile = File(...),
    _: None = Depends(require_api_key),
):
    require_acceptable_content_length(request)
        
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit.")
    image_array = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    
    if image is None:
        raise HTTPException(
            status_code=415,
            detail="The image could not be decoded. Use an ordinary JPG, PNG, or TIFF raster image.",
        )
    if image.shape[0] * image.shape[1] > MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=413, detail="Decoded image exceeds the pixel limit.")
        
    encoded_ok, encoded_img = cv2.imencode('.jpg', image)
    if not encoded_ok:
        raise HTTPException(status_code=500, detail="Image preview could not be encoded.")
    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

@app.get("/api/v1/stats")
async def get_stats(_: None = Depends(require_api_key)):
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
async def export_report(
    data: ResearchReportRequest,
    _: None = Depends(require_mutation_key),
):
    pdf = FPDF()
    pdf.add_page()
    
    filename = sanitize_pdf_text(data.filename)
    grade = sanitize_pdf_text(data.grade)
    hardware = sanitize_pdf_text(data.hardware)
    reviewer_name = sanitize_pdf_text(data.reviewer_name)
    count = data.count
    
    # Branded Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(
        0,
        10,
        text="TB-AFB RESEARCH INFERENCE REPORT",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.set_font("Helvetica", size=10)
    pdf.cell(
        0,
        10,
        text=f"Report ID: {uuid.uuid4().hex[:8].upper()}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(10)
    
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, text="RESEARCH SUMMARY", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", size=11)
    for line in (
        f"Analysis Target: {filename}",
        f"Research smear category: {grade}",
        f"AFB candidate count: {count}",
        f"Hardware Backend: {hardware}",
        f"Research reviewer: {reviewer_name}",
    ):
        pdf.cell(0, 8, text=line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(20)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 5, text=(
        "RESEARCH USE ONLY: This experimental output is not validated to diagnose "
        "tuberculosis, identify Mycobacterium tuberculosis, grade a clinical smear, "
        "or guide patient care. AFB microscopy is not species-specific."
    ))
    
    pdf_output = bytes(pdf.output())
    return Response(content=pdf_output, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=TB_AFB_Research_Report.pdf"})

WSI_HANDLES = OrderedDict()
MAX_WSI_HANDLES = int(os.getenv("TB_AFB_MAX_WSI_HANDLES", "4"))

@app.get("/api/v1/wsi/tile/{wsi_id}/{z}/{x}/{y}")
async def get_wsi_tile(
    wsi_id: str,
    z: int,
    x: int,
    y: int,
    _: None = Depends(require_api_key),
):
    # Dynamic tile server for OpenSeadragon
    if not DeepZoomGenerator:
        raise HTTPException(status_code=501, detail="OpenSlide DeepZoom not available on this host.")
        
    # Security: Ensure WSI_ID is not a path injection
    # 🛡️ REMEDIATION: Force filename-only resolution and strict is_relative_to validation
    safe_wsi_id = Path(wsi_id).name
    if safe_wsi_id != wsi_id:
        raise HTTPException(status_code=400, detail="Invalid WSI identifier.")
    base_data_dir = (current_dir.parent.parent / "01_DATA" / "raw_tiles").resolve()
    wsi_path = (base_data_dir / safe_wsi_id).resolve()
    
    # Final Jail Check: Resulting path MUST be within base_data_dir
    try:
        if not wsi_path.is_relative_to(base_data_dir):
            raise HTTPException(status_code=403, detail="Airtight Jail Breach Attempt Blocked.")
    except AttributeError:
        if os.path.commonpath([str(wsi_path), str(base_data_dir)]) != str(base_data_dir):
            raise HTTPException(status_code=403, detail="Airtight Jail Breach Attempt Blocked.")
    
    if not wsi_path.is_file():
        raise HTTPException(status_code=404, detail="WSI file not found.")

    if wsi_id not in WSI_HANDLES:
        import openslide
        try:
            slide = openslide.OpenSlide(str(wsi_path))
            dz = DeepZoomGenerator(slide, tile_size=254, overlap=1, limit_bounds=False)
            WSI_HANDLES[wsi_id] = (slide, dz)
            while len(WSI_HANDLES) > MAX_WSI_HANDLES:
                _, (old_slide, _) = WSI_HANDLES.popitem(last=False)
                old_slide.close()
        except Exception:
            raise HTTPException(status_code=404, detail="WSI file not found or corrupted.")

    slide, dz = WSI_HANDLES.pop(wsi_id)
    WSI_HANDLES[wsi_id] = (slide, dz)
    try:
        tile = dz.get_tile(z, (x, y))
        buf = BytesIO()
        tile.save(buf, format='JPEG')
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Tile Coordinates.")
