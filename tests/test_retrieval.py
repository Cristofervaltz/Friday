"""Tests for the retrieval subsystem."""

from unittest.mock import MagicMock, patch

from src.tools.search_tool import SemanticSearchTool


@patch("src.tools.search_tool.CodeIndexer")
def test_semantic_search_tool(mock_indexer_class: MagicMock) -> None:
    """Test the semantic search tool execution."""
    mock_indexer = MagicMock()
    mock_indexer.search.return_value = [
        {"file": "test.py", "content": "print('hello')", "distance": 0.1}
    ]
    mock_indexer_class.return_value = mock_indexer

    tool = SemanticSearchTool()
    assert tool.name == "semantic_search"

    result = tool.execute(query="hello")
    assert result.success is True
    assert "test.py" in str(result.output)

    mock_indexer.search.assert_called_once_with("hello", n_results=3)


def test_semantic_search_tool_missing_query() -> None:
    """Test missing query handling."""
    tool = SemanticSearchTool()
    result = tool.execute()

    assert result.success is False
    assert "query is required" in str(result.error)


@patch("src.tools.search_tool.CodeIndexer")
def test_semantic_search_tool_empty_results(mock_indexer_class: MagicMock) -> None:
    """Test empty results handling."""
    mock_indexer = MagicMock()
    mock_indexer.search.return_value = []
    mock_indexer_class.return_value = mock_indexer

    tool = SemanticSearchTool()
    result = tool.execute(query="unknown")

    assert result.success is True
    assert "No relevant results found" in str(result.output)
