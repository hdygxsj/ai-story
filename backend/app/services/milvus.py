from dataclasses import dataclass
from typing import Any

from pymilvus import MilvusClient

from app.core.config import settings


@dataclass(frozen=True)
class MilvusHit:
    id: str
    distance: float
    metadata: dict[str, Any]


class MilvusRagStore:
    def __init__(self, uri: str | None = None, collection_name: str = "ai_story_rag_chunks") -> None:
        self.collection_name = collection_name
        self.client = MilvusClient(uri=uri or settings.milvus_uri)

    def ensure_collection(self, dimension: int) -> None:
        if self.client.has_collection(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            dimension=dimension,
            metric_type="COSINE",
            auto_id=False,
        )

    def upsert(
        self,
        *,
        chunk_id: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        self.ensure_collection(len(embedding))
        self.client.upsert(
            collection_name=self.collection_name,
            data=[{"id": chunk_id, "vector": embedding, **metadata}],
        )

    def search(self, *, query_embedding: list[float], limit: int = 8) -> list[MilvusHit]:
        self.ensure_collection(len(query_embedding))
        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_embedding],
            limit=limit,
            output_fields=["novel_id", "source_type", "source_id"],
        )
        return [
            MilvusHit(
                id=str(hit["id"]),
                distance=float(hit["distance"]),
                metadata={key: value for key, value in hit.get("entity", {}).items()},
            )
            for hit in results[0]
        ]
