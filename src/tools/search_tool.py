"""Semantic search tools for Friday."""

from typing import Any

from src.retrieval.indexer import CodeIndexer
from src.tools.base import BaseTool, ToolResult


class SemanticSearchTool(BaseTool):
    """Tool to search the workspace using semantic understanding (RAG)."""

    def __init__(self, workspace_path: str = ".") -> None:
        """Initialize the semantic search tool."""
        self.workspace_path = workspace_path
        self._indexer: CodeIndexer | None = None

    @property
    def name(self) -> str:
        return "semantic_search"

    @property
    def description(self) -> str:
        return (
            "Search the workspace code using semantic understanding (meaning) "
            'rather than exact keyword matches. Useful for finding "where is '
            'the user authentication logic?" or similar conceptual questions. '
            "Returns the most relevant code snippets."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The concept or question to search for.",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 3).",
                },
            },
            "required": ["query"],
        }

    def _get_indexer(self) -> CodeIndexer:
        """Lazy load the indexer."""
        if self._indexer is None:
            self._indexer = CodeIndexer()
            # In a real app we'd do this incrementally or async,
            # but for the tool we just make sure it's indexed.
            self._indexer.index_directory(self.workspace_path)
        return self._indexer

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the semantic search."""
        query = kwargs.get("query")
        if not query:
            return ToolResult(success=False, error="query is required")

        n_results = int(kwargs.get("n_results", 3))

        try:
            indexer = self._get_indexer()
            results = indexer.search(query, n_results=n_results)

            if not results:
                return ToolResult(success=True, output="No relevant results found.")

            formatted_output = f"Top {len(results)} results for '{query}':\n\n"
            for r in results:
                formatted_output += (
                    f"--- {r['file']} (Score: {1.0 - r['distance']:.2f}) ---\n"
                )
                formatted_output += f"{r['content']}\n\n"

            return ToolResult(success=True, output=formatted_output)

        except Exception as e:
            return ToolResult(success=False, error=f"Semantic search failed: {e}")
