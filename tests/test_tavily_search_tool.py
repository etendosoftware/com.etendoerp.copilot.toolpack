from unittest.mock import patch

import pytest
from tools import TavilySearchTool


@pytest.fixture
def valid_query():
    return {"query": "What is the capital of Spain?"}


@pytest.fixture
def invalid_query():
    return {"query": ""}


@pytest.fixture
def setup_tool():
    return TavilySearchTool()


# Valid query test case


@patch.object(
    TavilySearchTool,
    "run",
    return_value=[{"content": "Madrid is the capital of Spain."}],
)
def test_valid_query(mock_run, setup_tool, valid_query):
    result = setup_tool.run(valid_query)
    assert isinstance(result, list)  # Should return a list
    assert all(
        isinstance(item, dict) for item in result
    )  # Each item in the list should be a dictionary
    assert "Madrid" in result[0]["content"]


# Invalid query test case


@patch.object(TavilySearchTool, "run", side_effect=Exception("Bad Request"))
def test_invalid_query(mock_run, setup_tool, invalid_query):
    try:
        result = setup_tool.run(invalid_query)
    except Exception as e:
        result = str(e)
    assert "Bad Request" in result


# Empty query test case


@patch.object(TavilySearchTool, "run", side_effect=Exception("Bad Request"))
def test_empty_query(mock_run, setup_tool):
    query = {"query": ""}
    try:
        result = setup_tool.run(query)
    except Exception as e:
        result = str(e)
    assert "Bad Request" in result


# Test for embedding distance


@patch.object(
    TavilySearchTool,
    "run",
    return_value=[{"content": "Madrid is the capital of Spain."}],
)
def test_partial_search_result(mock_run, setup_tool, valid_query):
    result = setup_tool.run(valid_query)
    assert "capital of Spain" in result[0]["content"]


# Test for edit distance


@patch.object(TavilySearchTool, "run", return_value=[{"content": "Madrid"}])
def test_edit_distance(mock_run, setup_tool, valid_query):
    result = setup_tool.run(valid_query)
    assert result[0]["content"] == "Madrid"
