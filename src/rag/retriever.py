"""Retrieval layer used by agents: query one or more namespaces and format the hits for the prompt."""
from langchain_core.documents import Document

from src.core.config import load_config
from src.rag.vector_store import get_vectorstore


def retrieve(query: str, namespaces: list[str], k: int | None = None) -> list[Document]:
    k = k or load_config()["rag"]["top_k"]
    docs: list[Document] = []
    for ns in namespaces:
        docs.extend(get_vectorstore(ns).similarity_search(query, k=k))
    return docs


def format_context(docs: list[Document]) -> str:
    return "\n\n".join(f"[{i}] (source: {d.metadata.get('source', 'unknown')})\n{d.page_content}"
                       for i, d in enumerate(docs, 1))
