from abc import ABC, abstractmethod
from datetime import datetime, timezone

from .config import Settings
from .models import MaterialRecord, MaterialStatus


class MaterialRepository(ABC):
    @abstractmethod
    async def create(self, record: MaterialRecord) -> MaterialRecord: ...

    @abstractmethod
    async def list(self, approved_only: bool = False) -> list[MaterialRecord]: ...

    @abstractmethod
    async def get(self, material_id: str) -> MaterialRecord | None: ...

    @abstractmethod
    async def update_status(self, material_id: str, status: MaterialStatus) -> MaterialRecord | None: ...


class MemoryMaterialRepository(MaterialRepository):
    def __init__(self):
        self.records: dict[str, MaterialRecord] = {}

    async def create(self, record: MaterialRecord) -> MaterialRecord:
        self.records[record.id] = record
        return record

    async def list(self, approved_only: bool = False) -> list[MaterialRecord]:
        records = list(self.records.values())
        if approved_only:
            records = [item for item in records if item.status == "approved"]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    async def get(self, material_id: str) -> MaterialRecord | None:
        return self.records.get(material_id)

    async def update_status(self, material_id: str, status: MaterialStatus) -> MaterialRecord | None:
        record = self.records.get(material_id)
        if not record:
            return None
        record.status = status
        record.updated_at = datetime.now(timezone.utc)
        self.records[material_id] = record
        return record


class FirestoreMaterialRepository(MaterialRepository):
    def __init__(self, settings: Settings):
        from google.cloud.firestore_v1.async_client import AsyncClient

        self.client = AsyncClient(
            project=settings.firebase_project_id or None,
            database=settings.firestore_database_id,
        )
        self.collection = self.client.collection("materials")

    async def create(self, record: MaterialRecord) -> MaterialRecord:
        await self.collection.document(record.id).set(record.model_dump(mode="json"))
        return record

    async def list(self, approved_only: bool = False) -> list[MaterialRecord]:
        query = self.collection
        if approved_only:
            query = query.where("status", "==", "approved")
        documents = [document async for document in query.stream()]
        records = [MaterialRecord.model_validate(document.to_dict()) for document in documents]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    async def get(self, material_id: str) -> MaterialRecord | None:
        snapshot = await self.collection.document(material_id).get()
        return MaterialRecord.model_validate(snapshot.to_dict()) if snapshot.exists else None

    async def update_status(self, material_id: str, status: MaterialStatus) -> MaterialRecord | None:
        ref = self.collection.document(material_id)
        snapshot = await ref.get()
        if not snapshot.exists:
            return None
        await ref.update({"status": status, "updated_at": datetime.now(timezone.utc)})
        return await self.get(material_id)


def build_repository(settings: Settings) -> MaterialRepository:
    if settings.storage_backend.lower() == "firestore":
        return FirestoreMaterialRepository(settings)
    return MemoryMaterialRepository()

