"""Qdrant collection holding one vector per searchable passage, with ACL fields in the payload."""

from __future__ import annotations

import re
import uuid

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client import models as qm

PAYLOAD_INDEXES = ("access_level", "office", "type", "source_id", "document_id")


def point_id(passage_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, passage_id))


class VectorIndex:
    def __init__(self, client: QdrantClient, base_collection: str, model_name: str, dim: int):
        # One collection per embedding model, so switching models never mixes vector spaces.
        slug = re.sub(r"[^a-z0-9]+", "-", model_name.lower()).strip("-")
        self.client = client
        self.collection = f"{base_collection}__{slug}"
        self.dim = dim

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            self.collection, vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE)
        )
        for field in PAYLOAD_INDEXES:
            self.client.create_payload_index(self.collection, field, qm.PayloadSchemaType.KEYWORD)

    def upsert(self, payloads: list[dict], vectors: np.ndarray, batch: int = 256) -> None:
        for i in range(0, len(payloads), batch):
            points = [
                qm.PointStruct(id=point_id(p["passage_id"]), vector=v.tolist(), payload=p)
                for p, v in zip(payloads[i : i + batch], vectors[i : i + batch])
            ]
            self.client.upsert(self.collection, points=points, wait=True)

    def delete(self, passage_ids: list[str]) -> None:
        if passage_ids:
            self.client.delete(self.collection, points_selector=qm.PointIdsList(points=[point_id(p) for p in passage_ids]), wait=True)

    def search(self, vector: np.ndarray, flt: qm.Filter, limit: int) -> list[tuple[str, float]]:
        res = self.client.query_points(self.collection, query=vector.tolist(), query_filter=flt, limit=limit, with_payload=["passage_id"])
        return [(p.payload["passage_id"], float(p.score)) for p in res.points]

    def count(self) -> int:
        return self.client.count(self.collection, exact=True).count if self.client.collection_exists(self.collection) else 0
