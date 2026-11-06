import json
import os
from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from google.cloud import storage
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import vertexai
from pptx import Presentation
from vertexai.generative_models import GenerativeModel, Image, Part
from vertexai.preview.vision_models import ImageGenerationModel

load_dotenv()
load_dotenv("agents/atvos_agent/.env")

app = FastAPI(title="Atvos Content Agent API")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT_ID", ""))
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", os.getenv("GCP_REGION", "us-central1"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
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


def image_from_gcs(uri: str) -> Image:
    return Image.load_from_file(download_gcs_image(uri))


def download_gcs_image(uri: str) -> str:
    if not uri.startswith("gs://"):
        raise HTTPException(400, "reference_image_gcs_uri must be a gs:// URI")
    bucket_name, _, blob_name = uri[5:].partition("/")
    if not blob_name:
        raise HTTPException(400, "Invalid reference_image_gcs_uri")
    local_path = f"/tmp/{os.path.basename(blob_name)}"
    storage_client().bucket(bucket_name).blob(blob_name).download_to_filename(local_path)
    return local_path


def replace_placeholders(presentation: Presentation, values: dict[str, str]) -> None:
    for slide in presentation.slides:
        for shape in list(slide.shapes):
            if not getattr(shape, "has_text_frame", False):
                continue
            text = shape.text
            for key, value in values.items():
                text = text.replace("{{" + key + "}}", value)
            if text != shape.text:
                shape.text_frame.text = text


def insert_generated_image(
    presentation: Presentation,
    image_bytes: bytes,
    placeholder: str = "{{image}}",
) -> None:
    image_path = "/tmp/atvos-generated-image.png"
    with open(image_path, "wb") as image_file:
        image_file.write(image_bytes)

    for slide in presentation.slides:
        for shape in list(slide.shapes):
            if getattr(shape, "has_text_frame", False) and placeholder in shape.text:
                left, top, width, height = shape.left, shape.top, shape.width, shape.height
                slide.shapes._spTree.remove(shape._element)
                slide.shapes.add_picture(image_path, left, top, width=width, height=height)
                return


def generate_atvos_images(prompt: str) -> bytes:
    image_model = ImageGenerationModel.from_pretrained(IMAGE_MODEL)
    generated = image_model.generate_images(
        prompt=prompt,
        number_of_images=1,
        aspect_ratio="16:9",
        output_mime_type="image/png",
    )
    if not generated.images:
        raise HTTPException(502, "Imagen 3 did not generate an image")
    image_path = "/tmp/atvos-imagen-output"
    generated.images[0].save(image_path)
    with open(image_path, "rb") as image_file:
        return image_file.read()


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
    presentation = Presentation(local_template)
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
    required = {"title", "body", "image_prompt"}
    if not required.issubset(content):
        raise HTTPException(502, "Gemini response must include title, body and image_prompt")

    replace_placeholders(
        presentation,
        {
            "title": str(content["title"]),
            "body": str(content["body"]),
        },
    )
    image_prompt = (
        "Atvos corporate communication. "
        f"{content['image_prompt']} Warm natural sunlight, sugarcane fields or "
        "bioenergy infrastructure, professional Brazilian corporate photography, "
        "energetic and clean, no text, no logo."
    )
    generated_image = generate_atvos_images(image_prompt)
    insert_generated_image(presentation, generated_image)

    draft_id = request.campaign_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    local_draft = f"/tmp/{draft_id}-draft.pptx"
    presentation.save(local_draft)
    draft_blob = bucket.blob(f"drafts/{draft_id}.pptx")
    draft_blob.upload_from_filename(local_draft)
    draft_blob.metadata = {"status": "Draft", "campaign_id": draft_id}
    draft_blob.patch()
    return {"draft_id": draft_id, "status": "Draft", "object": draft_blob.name}


@app.post("/review/{draft_id}")
def review(draft_id: str, request: ReviewRequest) -> dict[str, str]:
    bucket = storage_client().bucket(require_bucket())
    draft = bucket.blob(f"drafts/{draft_id}.pptx")
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
        approved = bucket.rename_blob(draft, f"approved/{draft_id}.pptx")
        approved.metadata = {**(approved.metadata or {}), "status": "Approved"}
        approved.patch()
    return {
        "draft_id": draft_id,
        "status": request.status,
        "feedback": "" if request.status == "Approved" else request.note,
    }


@app.get("/review/{draft_id}")
def review_status(draft_id: str) -> dict[str, str]:
    draft = storage_client().bucket(require_bucket()).blob(f"drafts/{draft_id}.pptx")
    if not draft.exists():
        raise HTTPException(404, "Draft not found")
    draft.reload()
    return {"draft_id": draft_id, **(draft.metadata or {})}
