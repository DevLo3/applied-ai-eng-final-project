from __future__ import annotations

import io
import os
import re
from pathlib import Path

import chromadb
import httpx

DOCS_DIR = Path(__file__).parent / "docs"
CHROMA_DIR = DOCS_DIR / "chroma_db"

_EMBED_MODEL = "gemini-embedding-001"   # "Gemini Embedding 1" in AI Studio
_GEN_MODEL = "gemini-2.5-flash"         # "Gemini 2.5 Flash" in AI Studio
_EMBED_URL = (
    "https://generativelanguage.googleapis.com"
    "/v1beta/models/{model}:embedContent"
)


def _api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("GEMINI_API_KEY is not set.")
    return key


def _embed(texts: list[str]) -> list[list[float]]:
    """Call the REST embedContent endpoint once per text and return float vectors.

    Using the REST endpoint directly because the google-genai SDK >=1.x routes
    embed_content to batchEmbedContents, which is not supported by text-embedding-004.
    """
    key = _api_key()
    url = _EMBED_URL.format(model=_embed_model())
    vectors: list[list[float]] = []
    for text in texts:
        body = {
            "model": f"models/{_embed_model()}",
            "content": {"parts": [{"text": text}]},
        }
        r = httpx.post(url, json=body, params={"key": key}, timeout=30)
        r.raise_for_status()
        vectors.append(r.json()["embedding"]["values"])
    return vectors


def _embed_model() -> str:
    return _EMBED_MODEL


def _gemini_client():
    from google import genai
    return genai.Client(api_key=_api_key())


def _chroma_client() -> chromadb.PersistentClient:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _collection_name(pet_name: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", pet_name.lower().strip())
    name = name.strip("-")
    name = f"pet-{name}"
    return name[:63] if len(name) >= 3 else name + "---"[:3 - len(name)]


def _extract_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == ".docx":
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    return file_bytes.decode("utf-8", errors="replace")


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 40) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i: i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def validate_key() -> None:
    """Raise an exception if the GEMINI_API_KEY cannot reach the Gemini API.

    Validates by calling the embedding endpoint directly — the same path used
    by ingest and query — so quota issues for generation models don't cause
    false negatives.
    """
    _embed(["test"])


def ingest(pet_name: str, file_bytes: bytes, filename: str) -> int:
    """Parse a document, embed its chunks, and upsert into the pet's ChromaDB collection.

    Returns the number of chunks stored.
    """
    chroma = _chroma_client()
    collection = chroma.get_or_create_collection(_collection_name(pet_name))

    text = _extract_text(file_bytes, filename)
    chunks = _chunk_text(text)
    if not chunks:
        return 0

    embeddings = _embed(chunks)

    base_id = Path(filename).stem
    ids = [f"{base_id}_chunk_{i}" for i in range(len(chunks))]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=[{"source": filename, "chunk": i} for i in range(len(chunks))],
    )
    return len(chunks)


def query(pet_name: str, question: str, top_k: int = 5, general_knowledge: bool = False) -> tuple[str, list[str]]:
    """Retrieve the most relevant document chunks and generate an answer with Gemini.

    Returns (answer_text, list_of_source_filenames).
    """
    chroma = _chroma_client()

    try:
        collection = chroma.get_collection(_collection_name(pet_name))
    except Exception:
        return f"No documents have been uploaded for {pet_name} yet.", []

    if collection.count() == 0:
        return f"No documents have been uploaded for {pet_name} yet.", []

    q_embedding = _embed([question])[0]

    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas"],
    )

    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []

    if not docs:
        return "No relevant information was found in the uploaded documents.", []

    sources = sorted({m["source"] for m in metas})
    context = "\n\n---\n\n".join(docs)

    if general_knowledge:
        instruction = (
            f"Answer the question about {pet_name}.\n"
            f"Prioritize information from the provided documents when relevant.\n"
            f"If the documents don't cover the question, use your general knowledge "
            f"and clearly indicate that you are doing so."
        )
    else:
        instruction = (
            f"Answer the question about {pet_name} using only the documents provided below.\n"
            f"If the answer is not contained in the documents, say so clearly."
        )

    prompt = (
        f"You are a helpful assistant for a pet care app called PawPal+.\n"
        f"{instruction}\n\n"
        f"Documents:\n{context}\n\n"
        f"Question: {question}\n\n"
        f"Answer:"
    )

    client = _gemini_client()
    gen_response = client.models.generate_content(model=_GEN_MODEL, contents=prompt)
    return gen_response.text, sources


def list_sources(pet_name: str) -> list[str]:
    """Return the unique filenames already ingested for a pet."""
    chroma = _chroma_client()
    try:
        collection = chroma.get_collection(_collection_name(pet_name))
    except Exception:
        return []
    if collection.count() == 0:
        return []
    results = collection.get(include=["metadatas"])
    return sorted({m["source"] for m in results["metadatas"]})
