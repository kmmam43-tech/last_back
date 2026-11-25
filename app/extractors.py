from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile


async def extract_text(file: UploadFile, max_size_mb: int) -> str:
    data = await file.read()
    if len(data) > max_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="업로드 파일이 허용 크기를 초과했습니다.")
    suffix = Path(file.filename or "").suffix.lower()
    try:
        if suffix in {".txt", ".md"}:
            return data.decode("utf-8-sig")
        if suffix == ".pdf":
            from pypdf import PdfReader

            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
        if suffix == ".docx":
            from docx import Document

            return "\n".join(paragraph.text for paragraph in Document(BytesIO(data)).paragraphs)
        if suffix == ".pptx":
            from pptx import Presentation

            presentation = Presentation(BytesIO(data))
            return "\n".join(
                shape.text
                for slide in presentation.slides
                for shape in slide.shapes
                if hasattr(shape, "text")
            )
    except Exception as exc:
        raise HTTPException(status_code=422, detail="파일 내용을 읽을 수 없습니다.") from exc
    raise HTTPException(status_code=415, detail="지원하지 않는 파일 형식입니다.")

