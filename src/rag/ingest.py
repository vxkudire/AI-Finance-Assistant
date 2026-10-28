"""Ingestion pipeline: load -> chunk -> embed -> upsert to Pinecone.

Layout:  knowledge_base/<namespace>/<files .md|.txt|.pdf>      (folder name == Pinecone namespace)
Run:     python -m src.rag.ingest
Chunk ids are deterministic, so re-running updates in place instead of duplicating.
"""
import argparse
import hashlib
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from src.core.config import ROOT, load_config
from src.rag.vector_store import get_vectorstore
from src.utils.logger import get_logger

log = get_logger("rag.ingest")


def load_namespace_docs(kb_dir: Path) -> dict:
    out = {}
    for ns_dir in sorted(p for p in kb_dir.iterdir() if p.is_dir()):
        docs = []
        for f in sorted(ns_dir.rglob("*")):
            suffix = f.suffix.lower()
            if suffix in {".md", ".txt"}:
                loaded = [Document(page_content=f.read_text(encoding="utf-8"))]
            elif suffix == ".pdf":
                loaded = [Document(page_content=page.extract_text() or "", metadata={"page": i})
                          for i, page in enumerate(PdfReader(str(f)).pages)]
            else:
                continue
            for d in loaded:
                d.metadata.update(source=f.name, namespace=ns_dir.name)
            docs.extend(loaded)
        if docs:
            out[ns_dir.name] = docs
    return out


def ingest(kb_dir: str | None = None) -> None:
    rag = load_config()["rag"]
    kb = Path(kb_dir) if kb_dir else ROOT / rag["knowledge_base_dir"]
    splitter = RecursiveCharacterTextSplitter(chunk_size=rag["chunk_size"], chunk_overlap=rag["chunk_overlap"])
    for ns, docs in load_namespace_docs(kb).items():
        chunks = splitter.split_documents(docs)
        ids = [hashlib.md5(f"{ns}|{c.metadata['source']}|{i}".encode()).hexdigest() for i, c in enumerate(chunks)]
        get_vectorstore(ns).add_documents(chunks, ids=ids)
        log.info("namespace=%s docs=%d chunks=%d upserted", ns, len(docs), len(chunks))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingest the knowledge base into Pinecone")
    ap.add_argument("--dir", help="override knowledge base directory")
    ingest(ap.parse_args().dir)
