"""Pinecone access through the official SDK (no langchain-pinecone, so no simsimd and no Python-version cap).

PineconeStore exposes the two methods the rest of the project uses:
    add_documents(docs, ids)  and  similarity_search(query, k)
Each knowledge domain is a Pinecone namespace inside one serverless index.
"""
import os
import time
import uuid
from functools import lru_cache

from langchain_core.documents import Document
from pinecone import Pinecone, ServerlessSpec

from src.core.config import load_config
from src.core.llm_factory import get_embeddings

TEXT_KEY = "text"   # chunk text is stored in vector metadata so retrieval can rebuild the Document


def _get(obj, key):
    """Read a field from either a dict-like or an attribute-style SDK response object."""
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)


class PineconeStore:
    def __init__(self, index, embedding, namespace: str):
        self.index, self.embedding, self.namespace = index, embedding, namespace

    def add_documents(self, docs: list[Document], ids: list[str] | None = None, batch_size: int = 100) -> list[str]:
        ids = ids or [uuid.uuid4().hex for _ in docs]
        for start in range(0, len(docs), batch_size):
            batch = docs[start:start + batch_size]
            vectors = self.embedding.embed_documents([d.page_content for d in batch])
            self.index.upsert(
                vectors=[{"id": ids[start + i], "values": vec, "metadata": {**d.metadata, TEXT_KEY: d.page_content}}
                         for i, (d, vec) in enumerate(zip(batch, vectors))],
                namespace=self.namespace,
            )
        return ids

    def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        res = self.index.query(vector=self.embedding.embed_query(query), top_k=k,
                               namespace=self.namespace, include_metadata=True)
        docs = []
        for m in _get(res, "matches"):
            meta = dict(_get(m, "metadata") or {})
            text = meta.pop(TEXT_KEY, "")
            meta["score"] = _get(m, "score")
            docs.append(Document(page_content=text, metadata=meta))
        return docs


@lru_cache(maxsize=1)
def _client() -> Pinecone:
    return Pinecone(api_key=os.environ["PINECONE_API_KEY"])


@lru_cache(maxsize=1)
def ensure_index() -> str:
    cfg = load_config()
    p, name, pc = cfg["pinecone"], cfg["pinecone"]["index_name"], _client()
    if not pc.has_index(name):
        pc.create_index(
            name=name,
            dimension=cfg["embeddings"]["dimension"],   # must equal the embedding model's output size
            metric=p.get("metric", "cosine"),
            spec=ServerlessSpec(cloud=p["cloud"], region=p["region"]),
        )
        while not _get(_get(pc.describe_index(name), "status"), "ready"):
            time.sleep(1)
    return name


@lru_cache(maxsize=None)
def get_vectorstore(namespace: str) -> PineconeStore:
    return PineconeStore(_client().Index(ensure_index()), get_embeddings(), namespace)
