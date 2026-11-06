from langchain_core.documents import Document

from src.rag.ingest import load_namespace_docs
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

    def query(self, *, top_k, vector, namespace="", include_metadata=False, filter=None):
        items = list(self.data.get(namespace, {}).values())
        if filter:
            category = filter["category"]["$eq"]
            items = [item for item in items if item["metadata"].get("category") == category]
        items = items[:top_k]
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


def test_category_filter_returns_only_matching_documents():
    idx = FakeIndex()
    store = PineconeStore(idx, FakeEmbeddings(), "finance_qa")
    store.add_documents([
        Document(page_content="Budgeting basics", metadata={"category": "budgeting"}),
        Document(page_content="Bond basics", metadata={"category": "investing"}),
    ], ids=["budget", "investing"])

    hits = store.similarity_search("basics", category="budgeting")

    assert [doc.page_content for doc in hits] == ["Budgeting basics"]


def test_ingestion_assigns_category_from_markdown_heading(tmp_path):
    finance_dir = tmp_path / "finance_qa"
    finance_dir.mkdir()
    (finance_dir / "budgeting.md").write_text("# Budgeting and Credit\nArticle text", encoding="utf-8")

    docs = load_namespace_docs(tmp_path)["finance_qa"]

    assert docs[0].metadata["category"] == "budgeting-and-credit"


def test_add_documents_generates_ids_and_handles_empty_batches():
    store = PineconeStore(FakeIndex(), FakeEmbeddings(), "tax")

    ids = store.add_documents([Document(page_content="Roth basics")])
    assert len(ids) == 1
    assert store.similarity_search("Roth")[0].page_content == "Roth basics"
    assert store.add_documents([]) == []


def test_ensure_index_creates_missing_index_without_external_service(monkeypatch):
    from src.rag import vector_store

    class FakePinecone:
        def __init__(self):
            self.created = None

        def has_index(self, name):
            return False

        def create_index(self, **kwargs):
            self.created = kwargs

        def describe_index(self, name):
            return {"status": {"ready": True}}

    client = FakePinecone()
    vector_store.ensure_index.cache_clear()
    monkeypatch.setattr(vector_store, "_client", lambda: client)
    monkeypatch.setattr(vector_store, "load_config", lambda: {
        "pinecone": {"index_name": "finance", "cloud": "aws", "region": "us-east-1"},
        "embeddings": {"dimension": 3},
    })
    monkeypatch.setattr(vector_store, "ServerlessSpec", lambda **kwargs: kwargs)

    try:
        assert vector_store.ensure_index() == "finance"
        assert client.created == {
            "name": "finance", "dimension": 3, "metric": "cosine",
            "spec": {"cloud": "aws", "region": "us-east-1"},
        }
    finally:
        vector_store.ensure_index.cache_clear()


def test_get_vectorstore_reuses_cached_namespace_client(monkeypatch):
    from src.rag import vector_store

    fake_index = object()
    monkeypatch.setattr(vector_store, "_client", lambda: type(
        "Client", (), {"Index": lambda self, name: fake_index}
    )())
    monkeypatch.setattr(vector_store, "ensure_index", lambda: "finance")
    monkeypatch.setattr(vector_store, "get_embeddings", FakeEmbeddings)
    vector_store.get_vectorstore.cache_clear()

    try:
        first = vector_store.get_vectorstore("tax")
        second = vector_store.get_vectorstore("tax")
        assert first is second
        assert first.index is fake_index
        assert first.namespace == "tax"
    finally:
        vector_store.get_vectorstore.cache_clear()
