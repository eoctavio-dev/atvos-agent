import json
import os
from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from google.cloud import storage
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from docx import Document
import vertexai
from vertexai.generative_models import GenerativeModel, Image, Part

load_dotenv()
load_dotenv("agents/atvos_agent/.env")

app = FastAPI(title="Atvos Content Agent API")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT_ID", ""))
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("GCP_REGION", "us-central1"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")


def storage_client() -> storage.Client:
    return storage.Client(project=PROJECT_ID or None)


class GenerateRequest(BaseModel):
    template_name: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    campaign_id: str | None = None
    reference_image_gcs_uri: str | None = None
    reference_image_bytes: bytes | None = None


class ReviewRequest(BaseModel):
    status: Literal["Approved", "Rejected"]
    reviewer: str
    note: str = ""


def require_bucket() -> str:
    if not BUCKET_NAME:
        raise HTTPException(503, "GCS_BUCKET_NAME is not configured")
    return BUCKET_NAME


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate")
def generate(request: GenerateRequest) -> dict[str, str]:
    bucket_name = require_bucket()
    bucket = storage_client().bucket(bucket_name)
    template_name = request.template_name
    if not template_name.startswith("templates/"):
        template_name = f"templates/{template_name}"
    template = bucket.blob(template_name)
    if not template.exists():
        raise HTTPException(404, "Template not found")

    local_template = f"/tmp/{os.path.basename(request.template_name)}"
    template.download_to_filename(local_template)
    document = Document(local_template)
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    model = GenerativeModel(MODEL)
    parts: list[object] = [request.prompt]
    if request.reference_image_gcs_uri:
        parts.append(Part.from_uri(request.reference_image_gcs_uri, mime_type="image/png"))
    elif request.reference_image_bytes:
        parts.append(Image.from_bytes(request.reference_image_bytes))
    response = model.generate_content(parts)
    content_text = response.text.strip()
    if content_text.startswith("```"):
        content_text = content_text.split("```", 2)[1].removeprefix("json").strip()
    try:
        content = json.loads(content_text)
    except json.JSONDecodeError as error:
        raise HTTPException(502, "Gemini returned invalid JSON") from error
    for paragraph in document.paragraphs:
        for key, value in content.items():
            placeholder = "{{" + str(key) + "}}"
            if placeholder in paragraph.text:
                paragraph.text = paragraph.text.replace(placeholder, str(value))

    draft_id = request.campaign_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    local_draft = f"/tmp/{draft_id}-draft.docx"
    document.save(local_draft)
    draft_blob = bucket.blob(f"drafts/{draft_id}.docx")
    draft_blob.upload_from_filename(local_draft)
    draft_blob.metadata = {"status": "Draft", "campaign_id": draft_id}
    draft_blob.patch()
    return {"draft_id": draft_id, "status": "Draft", "object": draft_blob.name}


@app.post("/review/{draft_id}")
def review(draft_id: str, request: ReviewRequest) -> dict[str, str]:
    bucket = storage_client().bucket(require_bucket())
    draft = bucket.blob(f"drafts/{draft_id}.docx")
    if not draft.exists():
        raise HTTPException(404, "Draft not found")
    draft.reload()
    draft.metadata = {
        "status": request.status,
        "reviewer": request.reviewer,
        "review_note": request.note,
    }
    draft.patch()
    if request.status == "Approved":
        approved = bucket.rename_blob(draft, f"approved/{draft_id}.docx")
        approved.metadata = {**(approved.metadata or {}), "status": "Approved"}
        approved.patch()
    return {
        "draft_id": draft_id,
        "status": request.status,
        "feedback": "" if request.status == "Approved" else request.note,
    }


@app.get("/review/{draft_id}")
def review_status(draft_id: str) -> dict[str, str]:
    draft = storage_client().bucket(require_bucket()).blob(f"drafts/{draft_id}.docx")
    if not draft.exists():
        raise HTTPException(404, "Draft not found")
    draft.reload()
    return {"draft_id": draft_id, **(draft.metadata or {})}
