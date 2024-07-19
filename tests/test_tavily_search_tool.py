import pytest
from langsmith import unit, expect

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
@unit
def test_valid_query(setup_tool, valid_query):
    result = setup_tool.run(valid_query)
    assert isinstance(result, list)  # Ajustado para lista
    assert all(isinstance(item, dict) for item in result)  # Cada item debe ser un diccionario
    expect.value(result[0]['content']).to_contain("Madrid")


# Invalid query test case
@unit
def test_invalid_query(setup_tool, invalid_query):
    try:
        result = setup_tool.run(invalid_query)
    except Exception as e:
        result = str(e)
    expect.value(result).to_contain("Bad Request")


# Empty query test case
@unit
def test_empty_query(setup_tool):
    query = {"query": ""}
    try:
        result = setup_tool.run(query)
    except Exception as e:
        result = str(e)
    expect.value(result).to_contain("Bad Request")


# Test for embedding distance
@unit
def test_partial_search_result(setup_tool, valid_query):
    result = setup_tool.run(valid_query)
    expect.embedding_distance(
        prediction=str(result[0]['content']),
        reference="capital of Spain"
    ).to_be_less_than(0.5)


# Test for edit distance
@unit
def test_edit_distance(setup_tool, valid_query):
    result = setup_tool.run(valid_query)
    expect.edit_distance(
        prediction=str(result[0]['content']),
        reference="Madrid"
    ).to_be_less_than(5)
