"""
One-shot script: read every markdown file under ../data, embed it with
Azure OpenAI text-embedding-3-small, and upload to the Azure AI Search
index `northwind-kb`.

Run AFTER `azd up` has provisioned the resources and you've exported
the azd environment to `.env`:

    azd env get-values > .env
    python app/seed_index.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from dotenv import load_dotenv
from openai import AzureOpenAI


INDEX_NAME = "northwind-kb"
EMBED_DIMS = 1536  # text-embedding-3-small


def _aoai_client() -> AzureOpenAI:
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_ad_token_provider=token_provider,
        api_version="2024-08-01-preview",
    )


def _ensure_index() -> None:
    endpoint = os.environ["AZURE_AI_SEARCH_ENDPOINT"]
    cred = DefaultAzureCredential()
    idx_client = SearchIndexClient(endpoint=endpoint, credential=cred)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBED_DIMS,
            vector_search_profile_name="default-hnsw",
        ),
    ]
    vector = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
        profiles=[VectorSearchProfile(name="default-hnsw", algorithm_configuration_name="default-hnsw")],
    )
    idx_client.create_or_update_index(SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector))


def _embed(client: AzureOpenAI, deployment: str, texts: Iterable[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=deployment, input=list(texts))
    return [item.embedding for item in resp.data]


def _load_docs(data_dir: Path) -> list[dict]:
    docs: list[dict] = []
    for md in sorted(data_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip() if text else md.stem
        docs.append({
            "id": md.stem,
            "source": md.name,
            "title": title,
            "content": text,
        })
    return docs


def main() -> None:
    load_dotenv()
    here = Path(__file__).resolve().parent
    data_dir = here.parent / "data"

    print(f"Ensuring search index '{INDEX_NAME}'…")
    _ensure_index()

    print(f"Loading docs from {data_dir} …")
    docs = _load_docs(data_dir)
    print(f"  {len(docs)} document(s) found.")

    print("Generating embeddings…")
    aoai = _aoai_client()
    embedding_deployment = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
    embeddings = _embed(aoai, embedding_deployment, (d["content"] for d in docs))
    for doc, vec in zip(docs, embeddings):
        doc["embedding"] = vec

    print("Uploading to Azure AI Search…")
    search = SearchClient(
        endpoint=os.environ["AZURE_AI_SEARCH_ENDPOINT"],
        index_name=INDEX_NAME,
        credential=DefaultAzureCredential(),
    )
    result = search.upload_documents(documents=docs)
    print(f"  {sum(1 for r in result if r.succeeded)}/{len(docs)} uploaded successfully.")


if __name__ == "__main__":
    main()
