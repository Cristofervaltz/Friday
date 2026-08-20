"""Code indexer and local vector database for Friday."""

import logging
from pathlib import Path
from typing import Any

from src.config import get_app_home

try:
    import chromadb  # type: ignore[import-not-found]
    from chromadb.config import Settings  # type: ignore[import-not-found]
    from sentence_transformers import (  # type: ignore[import-not-found]
        SentenceTransformer,
    )

    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False

logger = logging.getLogger("friday.retrieval")

# Files we want to index
SUPPORTED_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".cpp",
    ".h",
}

# Directories to ignore
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
}


class CodeIndexer:
    """Indexes workspace files into a local ChromaDB instance."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize the indexer.

        Args:
            db_path: Path to store the ChromaDB database.
        """
        if not _RAG_AVAILABLE:
            raise RuntimeError(
                "RAG dependencies not installed. Run: pip install .[rag]"
            )

        if db_path is None:
            self.db_path = get_app_home() / "chroma_db"
        else:
            self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initializing ChromaDB at {self.db_path.absolute()}")
        self.client = chromadb.PersistentClient(
            path=str(self.db_path), settings=Settings(anonymized_telemetry=False)
        )

        # Load the sentence transformer model for local embeddings
        # all-MiniLM-L6-v2 is small, fast, and works offline
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.collection = self.client.get_or_create_collection(name="workspace_code")

    def _chunk_text(
        self, text: str, chunk_size: int = 1000, overlap: int = 200
    ) -> list[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)

            # If not at the end, try to find a newline to break at
            if end < text_len:
                newline_idx = text.rfind("\n", start, end)
                if newline_idx != -1 and newline_idx > start + chunk_size // 2:
                    end = newline_idx + 1

            chunks.append(text[start:end])
            start = end - overlap

            if start < 0:
                start = 0

            # To avoid infinite loop if overlap >= chunk size
            if start >= end:
                break

        return chunks

    def index_directory(self, directory: str) -> int:
        """Index all supported files in a directory.

        Args:
            directory: The root directory to index.

        Returns:
            The number of chunks indexed.
        """
        root_path = Path(directory)
        documents: list[str] = []
        metadatas: list[dict[str, str | int | float | bool]] = []
        ids: list[str] = []

        chunk_count = 0

        logger.info(f"Scanning directory {root_path} for indexing...")
        for file_path in root_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip ignored directories
            if any(part in IGNORE_DIRS for part in file_path.parts):
                continue

            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")

                # Skip empty files
                if not content.strip():
                    continue

                chunks = self._chunk_text(content)

                for i, chunk in enumerate(chunks):
                    chunk_id = f"{file_path.relative_to(root_path)}#{i}"
                    documents.append(chunk)
                    metadatas.append(
                        {
                            "file": str(file_path.relative_to(root_path)),
                            "chunk_index": i,
                        }
                    )
                    ids.append(chunk_id)
                    chunk_count += 1

            except UnicodeDecodeError:
                logger.debug(f"Skipping binary/unreadable file: {file_path}")
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")

        # Batch insert into ChromaDB
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]
            batch_ids = ids[i : i + batch_size]
            batch_metadatas = metadatas[i : i + batch_size]

            # Compute embeddings locally
            embeddings = self.model.encode(batch_docs).tolist()

            self.collection.upsert(
                documents=batch_docs,
                embeddings=embeddings,
                metadatas=batch_metadatas,  # type: ignore[arg-type]
                ids=batch_ids,
            )

        logger.info(f"Successfully indexed {chunk_count} chunks from {root_path}")
        return chunk_count

    def search(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """Search the indexed code for a semantic query.

        Args:
            query: The search query (e.g., "Where is the database initialized?").
            n_results: Number of results to return.

        Returns:
            A list of dicts containing the file path, chunk content, and distance.
        """
        # Embed the query
        query_embedding = self.model.encode([query]).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding, n_results=n_results
        )

        formatted_results: list[dict[str, Any]] = []

        docs = results.get("documents")
        if not docs or not docs[0]:
            return formatted_results

        metas = results.get("metadatas")
        dists = results.get("distances")

        for i in range(len(docs[0])):
            doc = docs[0][i]

            # Safely get metadata
            meta = metas[0][i] if metas and metas[0] else None
            file_path = str(meta.get("file", "unknown")) if meta else "unknown"

            # Safely get distance
            dist = float(dists[0][i]) if dists and dists[0] else 0.0

            formatted_results.append(
                {"file": file_path, "content": doc, "distance": dist}
            )

        return formatted_results
