from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .agents_service import LearningMaterialAgents
from .config import Settings, get_settings
from .extractors import extract_text
from .models import MaterialRecord, MaterialRequest, StatusUpdate
from .repository import MaterialRepository, build_repository
from .workflow import build_workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.repository = build_repository(settings)
    app.state.agents = LearningMaterialAgents(settings)
    app.state.workflow = build_workflow(app.state.agents)
    yield


app = FastAPI(title="배움결 API", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def repository() -> MaterialRepository:
    return app.state.repository


@app.get("/health")
async def health(current: Settings = Depends(get_settings)):
    return {
        "status": "ok",
        "storage": current.storage_backend,
        "generation": "openai" if current.agents_enabled else "demo",
    }


@app.post("/api/materials/generate", response_model=MaterialRecord, status_code=201)
async def generate_material(
    title: str = Form(...),
    author: str = Form("교사"),
    grade: str = Form(...),
    language_level: str = Form(...),
    supports: str = Form(""),
    original_text: str = Form(""),
    file: UploadFile | None = File(default=None),
    repo: MaterialRepository = Depends(repository),
):
    source = original_text.strip()
    if file:
        source = (await extract_text(file, settings.max_upload_size_mb)).strip()
    request = MaterialRequest(
        title=title,
        author=author,
        grade=grade,
        language_level=language_level,
        supports=[item.strip() for item in supports.split(",") if item.strip()],
        original_text=source,
    )
    state = await app.state.workflow.ainvoke({"request": request})
    record = MaterialRecord(
        **request.model_dump(),
        analysis=state["analysis"],
        variants=state["bundle"].variants,
        reviews=state["reviews"],
        generation_mode="openai" if settings.agents_enabled else "demo",
    )
    return await repo.create(record)


@app.get("/api/materials", response_model=list[MaterialRecord])
async def list_materials(
    approved_only: bool = False,
    repo: MaterialRepository = Depends(repository),
):
    return await repo.list(approved_only=approved_only)


@app.get("/api/materials/{material_id}", response_model=MaterialRecord)
async def get_material(material_id: str, repo: MaterialRepository = Depends(repository)):
    record = await repo.get(material_id)
    if not record:
        raise HTTPException(status_code=404, detail="학습자료를 찾을 수 없습니다.")
    return record


@app.patch("/api/materials/{material_id}/status", response_model=MaterialRecord)
async def update_status(
    material_id: str,
    update: StatusUpdate,
    repo: MaterialRepository = Depends(repository),
):
    record = await repo.update_status(material_id, update.status)
    if not record:
        raise HTTPException(status_code=404, detail="학습자료를 찾을 수 없습니다.")
    return record

