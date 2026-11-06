from langchain_core.documents import Document

from src.rag import ingest, retriever


def test_retrieve_uses_config_default_and_queries_each_namespace(monkeypatch):
    calls = []

    class Store:
        def __init__(self, namespace):
            self.namespace = namespace

        def similarity_search(self, query, k, category):
            calls.append((self.namespace, query, k, category))
            return [Document(page_content=self.namespace, metadata={"source": f"{self.namespace}.md"})]

    monkeypatch.setattr(retriever, "load_config", lambda: {"rag": {"top_k": 3}})
    monkeypatch.setattr(retriever, "get_vectorstore", Store)

    docs = retriever.retrieve("retirement", ["tax", "finance_qa"], category="accounts")

    assert [doc.page_content for doc in docs] == ["tax", "finance_qa"]
    assert calls == [("tax", "retirement", 3, "accounts"),
                     ("finance_qa", "retirement", 3, "accounts")]
    assert retriever.format_context(docs).startswith("[1] (source: tax.md)")


def test_retrieve_falls_back_to_unknown_source(monkeypatch):
    monkeypatch.setattr(retriever, "get_vectorstore", lambda namespace: type(
        "Store", (), {"similarity_search": lambda self, query, k, category: [Document(page_content="text")]}
    )())
    context = retriever.format_context(retriever.retrieve("query", ["tax"], k=1))
    assert "(source: unknown)" in context


def test_load_namespace_docs_skips_unknown_files_and_handles_title_fallback(tmp_path):
    namespace = tmp_path / "tax"
    namespace.mkdir()
    (namespace / "capital_gains.md").write_text("Tax information without heading", encoding="utf-8")
    (namespace / "notes.bin").write_bytes(b"ignored")
    (tmp_path / "empty").mkdir()

    docs = ingest.load_namespace_docs(tmp_path)

    assert list(docs) == ["tax"]
    assert docs["tax"][0].metadata == {
        "source": "capital_gains.md", "namespace": "tax", "category": "capital-gains"
    }


def test_ingest_chunks_documents_and_uses_deterministic_ids(tmp_path, monkeypatch):
    namespace = tmp_path / "finance_qa"
    namespace.mkdir()
    (namespace / "guide.md").write_text("# Investing\n" + ("A useful finance lesson. " * 20), encoding="utf-8")
    monkeypatch.setattr(ingest, "load_config", lambda: {
        "rag": {"knowledge_base_dir": ".", "chunk_size": 60, "chunk_overlap": 0}
    })
    inserted = []

    class Store:
        def add_documents(self, docs, ids):
            inserted.append((docs, ids))

    monkeypatch.setattr(ingest, "get_vectorstore", lambda namespace: Store())

    ingest.ingest(str(tmp_path))
    ingest.ingest(str(tmp_path))

    assert len(inserted) == 2
    assert len(inserted[0][0]) > 1
    assert inserted[0][1] == inserted[1][1]
    assert all(doc.metadata["source"] == "guide.md" for doc in inserted[0][0])


def test_ingest_empty_directory_does_not_create_vectorstore(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "load_config", lambda: {
        "rag": {"knowledge_base_dir": ".", "chunk_size": 100, "chunk_overlap": 0}
    })
    monkeypatch.setattr(ingest, "get_vectorstore", lambda namespace: (_ for _ in ()).throw(AssertionError()))
    ingest.ingest(str(tmp_path))
