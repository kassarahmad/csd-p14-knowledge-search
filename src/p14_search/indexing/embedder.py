"""Text embedders. Models are small multilingual ones that fit an 8 GB GPU (ADR-005)."""

from __future__ import annotations

import hashlib
import re
import threading
from typing import Protocol

import numpy as np

# Instruction prefixes expected by each model family (from the model cards).
MODEL_PREFIXES = {
    "intfloat/multilingual-e5-small": ("query: ", "passage: "),
    "intfloat/multilingual-e5-base": ("query: ", "passage: "),
}


class Embedder(Protocol):
    name: str
    dim: int

    def embed_queries(self, texts: list[str]) -> np.ndarray: ...

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, device: str = "cuda", batch_size: int = 64):
        import torch
        from sentence_transformers import SentenceTransformer

        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        self.name = model_name
        self.model = SentenceTransformer(model_name, device=device)
        self.dim = self.model.get_sentence_embedding_dimension()
        self.batch_size = batch_size
        self.query_prefix, self.passage_prefix = MODEL_PREFIXES.get(model_name, ("", ""))
        self._lock = threading.Lock()

    def _encode(self, texts: list[str]) -> np.ndarray:
        with self._lock:
            return self.model.encode(
                texts, batch_size=self.batch_size, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
            ).astype(np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode([self.query_prefix + t for t in texts])

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._encode([self.passage_prefix + t for t in texts])


class HashingEmbedder:
    """Deterministic bag-of-words hashing embedder, for tests only (no model download)."""

    name = "test/hashing-256"
    dim = 256

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts])

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts])
