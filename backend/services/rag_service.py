"""Help answers from the written guide, not from the model's memory.

Viva: app_guide.md is cut into chunks and stored in ChromaDB.
A question finds the closest chunks. Gemini writes the answer using only those chunks.
That two-step process is RAG.
"""

from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import List

import chromadb
import google.generativeai as genai

from config import get_settings

RAG_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "rag_docs")
CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
COLLECTION_NAME = "app_help"
CHUNK_SIZE = 800  # characters per chunk
CHUNK_OVERLAP = 100


class RAGService:
    """Retrieval-Augmented Generation service using ChromaDB and Gemini."""

    def __init__(self) -> None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)

        self.model = genai.GenerativeModel(
            model_name="gemini-3.1-flash-lite",
            generation_config=genai.GenerationConfig(
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )

        # Persistent ChromaDB client
        self.client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Initialization – load documents
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Load all markdown files from *rag_docs/* into ChromaDB.

        Skips documents whose content hash is already present so repeated
        startups don't duplicate data.
        """
        docs_dir = Path(RAG_DOCS_DIR).resolve()
        if not docs_dir.exists():
            print(f"[RAG] rag_docs directory not found at {docs_dir}")
            return

        md_files = list(docs_dir.glob("*.md"))
        if not md_files:
            print("[RAG] No markdown files found in rag_docs/")
            return

        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # Check if this version is already indexed
            existing = self.collection.get(where={"source_hash": content_hash})
            if existing and existing["ids"]:
                print(f"[RAG] Skipping already-indexed file: {md_file.name}")
                continue

            # Remove old entries for the same source file
            try:
                old = self.collection.get(where={"source_file": md_file.name})
                if old and old["ids"]:
                    self.collection.delete(ids=old["ids"])
            except Exception:
                pass

            chunks = self._split_into_chunks(content)
            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict] = []

            for idx, chunk in enumerate(chunks):
                chunk_id = f"{md_file.stem}_{idx}_{content_hash[:8]}"
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append(
                    {
                        "source_file": md_file.name,
                        "source_hash": content_hash,
                        "chunk_index": idx,
                    }
                )

            if ids:
                self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
                print(f"[RAG] Indexed {len(ids)} chunks from {md_file.name}")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, question: str, n_results: int = 3) -> str:
        """Retrieve the most relevant document chunks for *question*."""
        try:
            results = self.collection.query(
                query_texts=[question],
                n_results=n_results,
            )
        except Exception:
            return ""

        if not results or not results["documents"] or not results["documents"][0]:
            return ""

        chunks = results["documents"][0]
        context = "\n\n---\n\n".join(chunks)
        return context

    def generate_help_response(self, question: str) -> str:
        """Use RAG context + Gemini to answer a help question."""
        context = self.query(question, n_results=5)

        prompt = (
            "You are a helpful assistant for a Student Management System application. "
            "Use the following documentation context to answer the user's question. "
            "If the context does not contain the answer, say so and provide general guidance.\n\n"
            f"DOCUMENTATION CONTEXT:\n{context}\n\n"
            f"USER QUESTION: {question}\n\n"
            "Provide a clear, helpful answer with step-by-step instructions when applicable."
        )

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as exc:
            return f"I'm sorry, I couldn't generate a help response at this time. Error: {exc}"

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _split_into_chunks(text: str) -> List[str]:
        """Split *text* into overlapping chunks."""
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks


# Module-level singleton
rag_service = RAGService()
