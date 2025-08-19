"""
Test suite for MemoryTool

This module contains comprehensive unit tests for the MemoryTool class,
covering all CRUD operations (Create, Read, Update, Delete) with proper
mocking of dependencies including ThreadContext and vector database operations.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools.MemoryTool import MemoryTool, MemoryToolInput, validate_and_process_input


@pytest.fixture
def setup_tool():
    """Create a MemoryTool instance for testing."""
    return MemoryTool()


@pytest.fixture
def mock_context_data():
    """Mock context data with assistant and user IDs."""
    return {"assistant_id": "test_assistant_123", "ad_user_id": "test_user_456"}


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store for testing."""
    mock_store = MagicMock()
    mock_store.add_documents = MagicMock()
    mock_store.similarity_search = MagicMock()
    mock_store.get = MagicMock()
    mock_store.update_documents = MagicMock()
    mock_store.delete = MagicMock()
    return mock_store


@pytest.fixture
def sample_memory_content():
    """Sample memory content for testing."""
    return "Remember to call John tomorrow at 3 PM about the project."


@pytest.fixture
def sample_memory_id():
    """Sample memory ID for testing."""
    return "mem_12345-67890-abcdef"


class TestMemoryToolInput:
    """Test cases for MemoryToolInput validation."""

    def test_valid_add_input(self):
        """Test valid input for add operation."""
        input_data = MemoryToolInput(mode="add", memory="Test memory")
        assert input_data.mode == "add"
        assert input_data.memory == "Test memory"
        assert input_data.query is None
        assert input_data.memory_id is None
        assert input_data.k == 3

    def test_valid_search_input(self):
        """Test valid input for search operation."""
        input_data = MemoryToolInput(mode="search", query="test query", k=5)
        assert input_data.mode == "search"
        assert input_data.query == "test query"
        assert input_data.k == 5
        assert input_data.memory is None
        assert input_data.memory_id is None

    def test_valid_update_input(self):
        """Test valid input for update operation."""
        input_data = MemoryToolInput(
            mode="update", memory="Updated content", memory_id="mem_123"
        )
        assert input_data.mode == "update"
        assert input_data.memory == "Updated content"
        assert input_data.memory_id == "mem_123"
        assert input_data.query is None

    def test_valid_delete_input(self):
        """Test valid input for delete operation."""
        input_data = MemoryToolInput(mode="delete", memory_id="mem_123")
        assert input_data.mode == "delete"
        assert input_data.memory_id == "mem_123"
        assert input_data.memory is None
        assert input_data.query is None


class TestValidateAndProcessInput:
    """Test cases for input validation function."""

    def test_valid_add_mode(self):
        """Test validation for add mode."""
        params = {"mode": "add", "memory": "Test memory", "k": 5}
        mode, memory, query, memory_id, k = validate_and_process_input(params)
        assert mode == "add"
        assert memory == "Test memory"
        assert query is None
        assert memory_id is None
        assert k == 5

    def test_valid_search_mode(self):
        """Test validation for search mode."""
        params = {"mode": "search", "query": "test query"}
        mode, _, query, _, k = validate_and_process_input(params)
        assert mode == "search"
        assert query == "test query"
        assert k == 3  # default value

    def test_invalid_mode(self):
        """Test validation with invalid mode."""
        params = {"mode": "invalid_mode"}
        with pytest.raises(ValueError) as exc_info:
            validate_and_process_input(params)
        assert "Invalid mode 'invalid_mode'" in str(exc_info.value)

    def test_default_k_value(self):
        """Test default k value when not provided."""
        params = {"mode": "search", "query": "test"}
        _, _, _, _, k = validate_and_process_input(params)
        assert k == 3


class TestMemoryToolAdd:
    """Test cases for add operation."""

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    @patch("tools.MemoryTool.uuid.uuid1")
    def test_add_success(
        self,
        mock_uuid,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
        sample_memory_content,
    ):
        """Test successful memory addition."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store
        mock_uuid.return_value = "generated_uuid_123"

        # Test parameters
        input_params = {"mode": "add", "memory": sample_memory_content}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "result" in result
        assert "Memory added for user_id test_user_456" in result["result"]
        assert "generated_uuid_123" in result["result"]
        mock_vector_store.add_documents.assert_called_once()

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_add_missing_memory(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
    ):
        """Test add operation with missing memory content."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Test parameters
        input_params = {"mode": "add"}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert "The 'memory' parameter is required for 'add' mode" in result["error"]

    @patch("tools.MemoryTool.ThreadContext.get_data")
    def test_add_missing_context(self, mock_get_data, setup_tool):
        """Test add operation with missing context variables."""
        # Setup mock to return None for context variables
        mock_get_data.return_value = None

        # Test parameters
        input_params = {"mode": "add", "memory": "Test memory"}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert "assistant_id or ad_user_id not found in Payload" in result["error"]


class TestMemoryToolSearch:
    """Test cases for search operation."""

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_search_success(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
    ):
        """Test successful memory search."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Mock search results
        mock_doc1 = MagicMock()
        mock_doc1.page_content = "Memory about meeting"
        mock_doc1.metadata = {"memory_id": "mem_123"}

        mock_doc2 = MagicMock()
        mock_doc2.page_content = "Memory about call"
        mock_doc2.metadata = {"memory_id": "mem_456"}

        mock_vector_store.similarity_search.return_value = [mock_doc1, mock_doc2]

        # Test parameters
        input_params = {"mode": "search", "query": "meeting", "k": 2}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "result" in result
        assert "Memory about meeting (memory_id: mem_123)" in result["result"]
        assert "Memory about call (memory_id: mem_456)" in result["result"]
        mock_vector_store.similarity_search.assert_called_once_with(
            query="meeting", k=2, filter={"user_id": "test_user_456"}
        )

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_search_no_results(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
    ):
        """Test search operation with no results."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store
        mock_vector_store.similarity_search.return_value = []

        # Test parameters
        input_params = {"mode": "search", "query": "nonexistent", "k": 3}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "result" in result
        assert (
            "No memories found for user_id test_user_456 with query: nonexistent"
            in result["result"]
        )

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_search_missing_query(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
    ):
        """Test search operation with missing query."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Test parameters
        input_params = {"mode": "search", "k": 3}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert "The 'query' parameter is required for 'search' mode" in result["error"]


class TestMemoryToolUpdate:
    """Test cases for update operation."""

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_update_success(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
        sample_memory_id,
    ):
        """Test successful memory update."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Mock existing memory
        mock_vector_store.get.return_value = {
            "ids": [sample_memory_id],
            "metadatas": [{"user_id": "test_user_456", "memory_id": sample_memory_id}],
        }

        # Test parameters
        input_params = {
            "mode": "update",
            "memory_id": sample_memory_id,
            "memory": "Updated memory content",
        }

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "result" in result
        assert "Memory updated for user_id test_user_456" in result["result"]
        assert "Updated memory content" in result["result"]
        mock_vector_store.update_documents.assert_called_once()

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_update_memory_not_found(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
        sample_memory_id,
    ):
        """Test update operation when memory doesn't exist."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Mock no existing memory
        mock_vector_store.get.return_value = {"ids": [], "metadatas": []}

        # Test parameters
        input_params = {
            "mode": "update",
            "memory_id": sample_memory_id,
            "memory": "Updated content",
        }

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert f"No memory found with memory_id {sample_memory_id}" in result["error"]

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_update_wrong_user(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
        sample_memory_id,
    ):
        """Test update operation when memory belongs to different user."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Mock memory belonging to different user
        mock_vector_store.get.return_value = {
            "ids": [sample_memory_id],
            "metadatas": [{"user_id": "different_user", "memory_id": sample_memory_id}],
        }

        # Test parameters
        input_params = {
            "mode": "update",
            "memory_id": sample_memory_id,
            "memory": "Updated content",
        }

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert f"No memory found with memory_id {sample_memory_id}" in result["error"]

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_update_missing_parameters(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
    ):
        """Test update operation with missing parameters."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Test parameters - missing memory_id
        input_params = {"mode": "update", "memory": "Updated content"}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert (
            "Both 'memory_id' and 'memory' are required for 'update' mode"
            in result["error"]
        )


class TestMemoryToolDelete:
    """Test cases for delete operation."""

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_delete_success(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
        sample_memory_id,
    ):
        """Test successful memory deletion."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Mock existing memory
        mock_vector_store.get.return_value = {
            "ids": [sample_memory_id],
            "metadatas": [{"user_id": "test_user_456", "memory_id": sample_memory_id}],
        }

        # Test parameters
        input_params = {"mode": "delete", "memory_id": sample_memory_id}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "result" in result
        assert (
            f"Memory with memory_id {sample_memory_id} deleted for user_id test_user_456"
            in result["result"]
        )
        mock_vector_store.delete.assert_called_once_with(ids=[sample_memory_id])

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_delete_memory_not_found(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
        sample_memory_id,
    ):
        """Test delete operation when memory doesn't exist."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Mock no existing memory
        mock_vector_store.get.return_value = {"ids": [], "metadatas": []}

        # Test parameters
        input_params = {"mode": "delete", "memory_id": sample_memory_id}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert f"No memory found with memory_id {sample_memory_id}" in result["error"]

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_delete_missing_memory_id(
        self,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
    ):
        """Test delete operation with missing memory_id."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store

        # Test parameters
        input_params = {"mode": "delete"}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert (
            "The 'memory_id' parameter is required for 'delete' mode" in result["error"]
        )


class TestMemoryToolErrorHandling:
    """Test cases for error handling."""

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    def test_vector_store_exception(
        self, mock_get_vector_store, mock_get_data, setup_tool, mock_context_data
    ):
        """Test handling of vector store exceptions."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.side_effect = Exception("Database connection failed")

        # Test parameters
        input_params = {"mode": "add", "memory": "Test memory"}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert "Error in MemoryTool: Database connection failed" in result["error"]

    def test_invalid_mode_error(self, setup_tool):
        """Test handling of invalid mode."""
        # Test parameters
        input_params = {"mode": "invalid_operation", "memory": "Test memory"}

        # Execute
        result = setup_tool.run(input_params)

        # Assertions
        assert "error" in result
        assert "Invalid mode 'invalid_operation'" in result["error"]


class TestMemoryToolIntegration:
    """Integration test cases."""

    @patch("tools.MemoryTool.ThreadContext.get_data")
    @patch("tools.MemoryTool.get_vector_store")
    @patch("tools.MemoryTool.uuid.uuid1")
    def test_full_memory_lifecycle(
        self,
        mock_uuid,
        mock_get_vector_store,
        mock_get_data,
        setup_tool,
        mock_context_data,
        mock_vector_store,
    ):
        """Test complete memory lifecycle: add, search, update, delete."""
        # Setup mocks
        mock_get_data.side_effect = lambda key, default=None: mock_context_data.get(
            key, default
        )
        mock_get_vector_store.return_value = mock_vector_store
        memory_id = "lifecycle_test_123"
        mock_uuid.return_value = memory_id

        # 1. Add memory
        add_params = {"mode": "add", "memory": "Initial memory content"}
        add_result = setup_tool.run(add_params)
        assert "result" in add_result
        assert "Memory added" in add_result["result"]

        # 2. Search memory
        mock_doc = MagicMock()
        mock_doc.page_content = "Initial memory content"
        mock_doc.metadata = {"memory_id": memory_id}
        mock_vector_store.similarity_search.return_value = [mock_doc]

        search_params = {"mode": "search", "query": "initial", "k": 1}
        search_result = setup_tool.run(search_params)
        assert "result" in search_result
        assert "Initial memory content" in search_result["result"]

        # 3. Update memory
        mock_vector_store.get.return_value = {
            "ids": [memory_id],
            "metadatas": [{"user_id": "test_user_456", "memory_id": memory_id}],
        }

        update_params = {
            "mode": "update",
            "memory_id": memory_id,
            "memory": "Updated content",
        }
        update_result = setup_tool.run(update_params)
        assert "result" in update_result
        assert "Memory updated" in update_result["result"]

        # 4. Delete memory
        delete_params = {"mode": "delete", "memory_id": memory_id}
        delete_result = setup_tool.run(delete_params)
        assert "result" in delete_result
        assert "Memory with memory_id" in delete_result["result"]
        assert "deleted" in delete_result["result"]
