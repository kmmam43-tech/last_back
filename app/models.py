from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


MaterialStatus = Literal["draft", "reviewing", "approved", "rejected"]


class MaterialRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    original_text: str = Field(min_length=20)
    author: str = Field(default="교사", max_length=80)
    grade: str = Field(min_length=1, max_length=40)
    language_level: str = Field(min_length=1, max_length=80)
    supports: list[str] = Field(default_factory=list, max_length=12)


class MaterialAnalysis(BaseModel):
    learning_objectives: list[str]
    core_concepts: list[str]
    essential_terms: list[str]
    assessment_requirements: list[str]
    access_barriers: list[str]


class WorksheetVariant(BaseModel):
    kind: Literal["easy_sentences", "key_terms", "short_paragraphs", "visual_worksheet"]
    title: str
    content: str
    image_prompt: str | None = None
    alt_text: str | None = None
    image_data_url: str | None = None


class VariantBundle(BaseModel):
    variants: list[WorksheetVariant] = Field(min_length=4)


class ReviewResult(BaseModel):
    reviewer: Literal[
        "subject_content_reviewer",
        "accessibility_reviewer",
        "student_perspective_reviewer",
    ]
    passed: bool
    score: int = Field(ge=0, le=100)
    summary: str
    issues: list[str] = Field(default_factory=list)


class MaterialRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    author: str
    grade: str
    language_level: str
    supports: list[str]
    original_text: str
    analysis: MaterialAnalysis
    variants: list[WorksheetVariant]
    reviews: list[ReviewResult]
    status: MaterialStatus = "reviewing"
    version: int = 1
    generation_mode: Literal["openai", "demo"] = "demo"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]

