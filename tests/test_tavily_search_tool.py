from unittest.mock import MagicMock, patch

import pytest
from tools import TavilySearchTool


@pytest.fixture
def setup_tool():
    return TavilySearchTool()


@pytest.fixture
def valid_query():
    return {"query": "What is the capital of Spain?"}


@patch("tools.TavilySearchTool.TavilySearchResults")
@patch("tools.TavilySearchTool.read_optional_env_var", return_value="fake_key")
def test_run_invokes_tavily(mock_env, mock_tavily_cls, setup_tool, valid_query):
    mock_tool_instance = MagicMock()
    mock_tool_instance.invoke.return_value = [{"content": "Madrid is the capital of Spain."}]
    mock_tavily_cls.return_value = mock_tool_instance

    result = setup_tool.run(valid_query)

    mock_tavily_cls.assert_called_once_with(tavily_api_key="fake_key")
    mock_tool_instance.invoke.assert_called_once_with({"query": "What is the capital of Spain?"})
    assert isinstance(result, list)
    assert "Madrid" in result[0]["content"]


@patch("tools.TavilySearchTool.TavilySearchResults")
@patch("tools.TavilySearchTool.read_optional_env_var", return_value=None)
def test_run_with_no_api_key(mock_env, mock_tavily_cls, setup_tool, valid_query):
    mock_tool_instance = MagicMock()
    mock_tool_instance.invoke.return_value = []
    mock_tavily_cls.return_value = mock_tool_instance

    result = setup_tool.run(valid_query)

    mock_tavily_cls.assert_called_once_with(tavily_api_key=None)
    assert result == []


@patch("tools.TavilySearchTool.TavilySearchResults")
@patch("tools.TavilySearchTool.read_optional_env_var", return_value="fake_key")
def test_run_with_empty_query(mock_env, mock_tavily_cls, setup_tool):
    mock_tool_instance = MagicMock()
    mock_tool_instance.invoke.return_value = []
    mock_tavily_cls.return_value = mock_tool_instance

    result = setup_tool.run({"query": ""})

    mock_tool_instance.invoke.assert_called_once_with({"query": ""})
    assert result == []


@patch("tools.TavilySearchTool.TavilySearchResults")
@patch("tools.TavilySearchTool.read_optional_env_var", return_value="fake_key")
def test_run_with_missing_query_key(mock_env, mock_tavily_cls, setup_tool):
    mock_tool_instance = MagicMock()
    mock_tool_instance.invoke.return_value = []
    mock_tavily_cls.return_value = mock_tool_instance

    result = setup_tool.run({})

    mock_tool_instance.invoke.assert_called_once_with({"query": None})
    assert result == []


@patch("tools.TavilySearchTool.TavilySearchResults")
@patch("tools.TavilySearchTool.read_optional_env_var", return_value="fake_key")
def test_run_returns_multiple_results(mock_env, mock_tavily_cls, setup_tool, valid_query):
    mock_tool_instance = MagicMock()
    mock_tool_instance.invoke.return_value = [
        {"content": "Result 1"},
        {"content": "Result 2"},
    ]
    mock_tavily_cls.return_value = mock_tool_instance

    result = setup_tool.run(valid_query)

    assert len(result) == 2
    assert result[0]["content"] == "Result 1"
    assert result[1]["content"] == "Result 2"
