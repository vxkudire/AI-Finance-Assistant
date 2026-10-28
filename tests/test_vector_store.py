from langchain_core.documents import Document

from src.rag.vector_store import PineconeStore


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[float(len(t)), 1.0] for t in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0]


class FakeIndex:
    """Mimics the bits of pinecone.Index the store uses."""
    def __init__(self):
        self.data = {}

    def upsert(self, *, vectors, namespace=""):
        for v in vectors:
            self.data.setdefault(namespace, {})[v["id"]] = v

    def query(self, *, top_k, vector, namespace="", include_metadata=False):
        items = list(self.data.get(namespace, {}).values())[:top_k]
        return {"matches": [{"id": v["id"], "score": 0.9, "metadata": v["metadata"]} for v in items]}


def test_roundtrip_and_namespace_isolation():
    idx = FakeIndex()
    tax = PineconeStore(idx, FakeEmbeddings(), "tax")
    qa = PineconeStore(idx, FakeEmbeddings(), "finance_qa")
    tax.add_documents([Document(page_content="Roth basics", metadata={"source": "a.md", "page": 0})], ids=["1"])
    hits = tax.similarity_search("roth", k=3)
    assert hits[0].page_content == "Roth basics"
    assert hits[0].metadata["source"] == "a.md" and hits[0].metadata["score"] == 0.9
    assert "text" not in hits[0].metadata          # text key is stripped back out of metadata
    assert qa.similarity_search("roth") == []      # other namespace sees nothing


def test_deterministic_ids_overwrite_instead_of_duplicate():
    idx = FakeIndex()
    s = PineconeStore(idx, FakeEmbeddings(), "tax")
    s.add_documents([Document(page_content="v1", metadata={"source": "a.md"})], ids=["x"])
    s.add_documents([Document(page_content="v2", metadata={"source": "a.md"})], ids=["x"])
    assert len(idx.data["tax"]) == 1 and s.similarity_search("q")[0].page_content == "v2"


def test_batching():
    idx = FakeIndex()
    s = PineconeStore(idx, FakeEmbeddings(), "n")
    s.add_documents([Document(page_content=f"d{i}", metadata={"source": "s"}) for i in range(250)], batch_size=100)
    assert len(idx.data["n"]) == 250
