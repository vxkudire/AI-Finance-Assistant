import argparse
import sys
from pathlib import Path
from src.core.config import load_config

print(str(Path(__file__).resolve().parents[1]))

# load yaml config and print it
d=load_config()
print(d["llm"]["provider"], d["llm"]["model"])
print(d.get("agents", {}).get("finance_qa", {}))

#get embeddings
embeddings = load_config()["embeddings"]
print(f"{embeddings['provider']}:{embeddings['model']}")

ap = argparse.ArgumentParser(description="Ingest the knowledge base into Pinecone")
ap.add_argument("--dir", help="override knowledge base directory")
print(ap.parse_args().dir)