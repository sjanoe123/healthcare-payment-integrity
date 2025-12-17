"""ChromaDB vector store for RAG."""

from __future__ import annotations

import os
from typing import Any

import chromadb
from chromadb.config import Settings


class ChromaStore:
    """Simple ChromaDB wrapper for policy document retrieval."""

    def __init__(
        self, persist_dir: str | None = None, collection_name: str = "policies"
    ):
        self.persist_dir = persist_dir or os.getenv(
            "CHROMA_PERSIST_DIR", "./data/chroma"
        )
        self.collection_name = collection_name

        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Healthcare policy documents for RAG"},
        )

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> None:
        """Add documents to the collection."""
        if not documents:
            return

        # Generate IDs if not provided
        if ids is None:
            existing_count = self.collection.count()
            ids = [f"doc_{existing_count + i}" for i in range(len(documents))]

        # Default metadata if not provided
        if metadatas is None:
            metadatas = [{"source": "unknown"} for _ in documents]

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    def search(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """Search for relevant documents."""
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        # Format results
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted.append(
                    {
                        "content": doc,
                        "metadata": results["metadatas"][0][i]
                        if results["metadatas"]
                        else {},
                        "distance": results["distances"][0][i]
                        if results["distances"]
                        else None,
                        "id": results["ids"][0][i] if results["ids"] else None,
                    }
                )

        return formatted

    def count(self) -> int:
        """Return number of documents in collection."""
        return self.collection.count()

    def clear(self) -> None:
        """Clear all documents from collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Healthcare policy documents for RAG"},
        )


# Global instance
_store: ChromaStore | None = None


def get_store() -> ChromaStore:
    """Get or create the global ChromaDB store."""
    global _store
    if _store is None:
        _store = ChromaStore()
    return _store
