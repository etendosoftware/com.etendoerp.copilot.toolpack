"""
Test suite for EtendoSQLToCSVTool

This module contains comprehensive unit tests for the EtendoSQLToCSVTool class,
covering SQL query execution, JSON to CSV conversion, and error handling scenarios.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest
import requests

from tools.EtendoSQLToCSVTool import (
    EtendoSQLToCSVTool,
    EtendoSQLToCSVToolInput,
    convert_json_to_csv,
    execute_sql_query,
    validate_sql_query,
)


@pytest.fixture
def setup_tool():
    """Create an EtendoSQLToCSVTool instance for testing."""
    return EtendoSQLToCSVTool()


@pytest.fixture
def sample_json_data():
    """Sample JSON data that mimics Etendo webhook response."""
    return {
        "queryExecuted": "SELECT id, name, email FROM ad_user LIMIT 10",
        "columns": ["id", "name", "email"],
        "data": [
            [1, "John Doe", "john@example.com"],
            [2, "Jane Smith", "jane@example.com"],
            [3, "Bob Johnson", "bob@example.com"],
        ],
    }


@pytest.fixture
def sample_webhook_url():
    """Sample webhook URL for testing."""
    return "https://test-etendo.com/api/sqlexec"


@pytest.fixture
def sample_sql_query():
    """Sample SQL query for testing."""
    return "SELECT id, name, email FROM ad_user LIMIT 10"


class TestEtendoSQLToCSVToolInput:
    """Test cases for EtendoSQLToCSVToolInput validation."""

    def test_valid_input(self):
        """Test valid input creation."""
        input_data = EtendoSQLToCSVToolInput(
            sql_query="SELECT * FROM test",
            webhook_url="https://example.com/webhook",
            auth_token="test_token",
            include_headers=True,
        )
        assert input_data.sql_query == "SELECT * FROM test"
        assert input_data.webhook_url == "https://example.com/webhook"
        assert input_data.auth_token == "test_token"
        assert input_data.include_headers is True

    def test_minimal_input(self):
        """Test minimal required input."""
        input_data = EtendoSQLToCSVToolInput(
            sql_query="SELECT id FROM users", webhook_url="https://example.com/webhook"
        )
        assert input_data.sql_query == "SELECT id FROM users"
        assert input_data.webhook_url == "https://example.com/webhook"
        assert input_data.auth_token is None
        assert input_data.output_file is None
        assert input_data.include_headers is True


class TestValidateSQLQuery:
    """Test cases for SQL query validation."""

    def test_valid_select_query(self):
        """Test validation of valid SELECT queries."""
        valid_queries = [
            "SELECT * FROM users",
            "select id, name from customers where active = 1",
            "SELECT COUNT(*) FROM orders",
            "   SELECT distinct category FROM products   ",
        ]
        for query in valid_queries:
            assert validate_sql_query(query) is True

    def test_invalid_dangerous_queries(self):
        """Test rejection of dangerous SQL operations."""
        dangerous_queries = [
            "DROP TABLE users",
            "DELETE FROM customers",
            "INSERT INTO users VALUES (1, 'test')",
            "UPDATE users SET name = 'hacked'",
            "TRUNCATE TABLE orders",
            "ALTER TABLE users ADD COLUMN hacked VARCHAR(255)",
            "CREATE TABLE malicious (id INT)",
            "EXEC sp_malicious",
            "select * from users; DROP TABLE users;",
        ]
        for query in dangerous_queries:
            assert validate_sql_query(query) is False

    def test_non_select_queries(self):
        """Test rejection of non-SELECT queries."""
        non_select_queries = [
            "SHOW TABLES",
            "DESCRIBE users",
            "EXPLAIN SELECT * FROM users",
        ]
        for query in non_select_queries:
            assert validate_sql_query(query) is False


class TestExecuteSQLQuery:
    """Test cases for SQL query execution."""

    @patch("requests.post")
    def test_successful_query_execution(
        self, mock_post, sample_webhook_url, sample_sql_query, sample_json_data
    ):
        """Test successful SQL query execution."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = sample_json_data
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = execute_sql_query(sample_webhook_url, sample_sql_query, "test_token")

        assert result == sample_json_data
        mock_post.assert_called_once()

        # Verify request parameters
        call_args = mock_post.call_args
        assert call_args[1]["json"]["Query"] == sample_sql_query
        assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"

    @patch("requests.post")
    def test_query_execution_without_token(
        self, mock_post, sample_webhook_url, sample_sql_query, sample_json_data
    ):
        """Test SQL query execution without authentication token."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = sample_json_data
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = execute_sql_query(sample_webhook_url, sample_sql_query)

        assert result == sample_json_data

        # Verify no Authorization header was sent
        call_args = mock_post.call_args
        assert "Authorization" not in call_args[1]["headers"]

    @patch("requests.post")
    def test_http_error_handling(self, mock_post, sample_webhook_url, sample_sql_query):
        """Test handling of HTTP errors."""
        # Mock HTTP error
        mock_post.side_effect = requests.RequestException("Connection failed")

        with pytest.raises(requests.RequestException) as exc_info:
            execute_sql_query(sample_webhook_url, sample_sql_query)

        assert "Failed to execute SQL query" in str(exc_info.value)

    @patch("requests.post")
    def test_invalid_json_response(
        self, mock_post, sample_webhook_url, sample_sql_query
    ):
        """Test handling of invalid JSON responses."""
        # Mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with pytest.raises(ValueError) as exc_info:
            execute_sql_query(sample_webhook_url, sample_sql_query)

        assert "Invalid JSON response from webhook" in str(exc_info.value)


class TestConvertJSONToCSV:
    """Test cases for JSON to CSV conversion."""

    def test_successful_conversion_with_data_field(self, sample_json_data):
        """Test successful conversion with Etendo webhook response format."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as temp_file:
            temp_path = temp_file.name

        try:
            result_path = convert_json_to_csv(sample_json_data, temp_path, True)
            assert result_path == temp_path

            # Verify CSV content
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "id,name,email" in content
                assert "John Doe" in content
                assert "jane@example.com" in content
        finally:
            os.unlink(temp_path)

    def test_conversion_with_results_field(self):
        """Test conversion with legacy format (not used by Etendo but for compatibility)."""
        json_data = {
            "columns": ["product", "price"],
            "data": [
                ["Laptop", 999.99],
                ["Mouse", 29.99],
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as temp_file:
            temp_path = temp_file.name

        try:
            result_path = convert_json_to_csv(json_data, temp_path, True)
            assert result_path == temp_path

            # Verify CSV content
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "product,price" in content
                assert "Laptop" in content
        finally:
            os.unlink(temp_path)

    def test_conversion_without_headers(self, sample_json_data):
        """Test CSV conversion without headers."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as temp_file:
            temp_path = temp_file.name

        try:
            convert_json_to_csv(sample_json_data, temp_path, False)

            # Verify CSV content has no headers
            with open(temp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                assert not lines[0].startswith("id,name,email")
                assert "John Doe" in lines[0]
        finally:
            os.unlink(temp_path)

    def test_conversion_with_list_data(self):
        """Test conversion when JSON is in direct list format (not supported by Etendo)."""
        json_data = {
            "columns": ["status", "count"],
            "data": [
                ["active", 5],
                ["inactive", 2],
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as temp_file:
            temp_path = temp_file.name

        try:
            convert_json_to_csv(json_data, temp_path, True)

            # Verify CSV content
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "status,count" in content
                assert "active,5" in content
        finally:
            os.unlink(temp_path)

    def test_conversion_empty_data(self):
        """Test conversion with empty data."""
        json_data = {"columns": ["id", "name"], "data": []}

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as temp_file:
            temp_path = temp_file.name

        try:
            with pytest.raises(ValueError) as exc_info:
                convert_json_to_csv(json_data, temp_path, True)
            assert "No data returned from SQL query" in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_conversion_invalid_format(self):
        """Test conversion with invalid JSON format."""
        json_data = {"invalid": "format"}

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv"
        ) as temp_file:
            temp_path = temp_file.name

        try:
            with pytest.raises(ValueError) as exc_info:
                convert_json_to_csv(json_data, temp_path, True)
            assert "Invalid webhook response format" in str(exc_info.value)
        finally:
            os.unlink(temp_path)


class TestEtendoSQLToCSVTool:
    """Test cases for the main tool class."""

    @patch("tools.EtendoSQLToCSVTool.execute_sql_query")
    @patch("tools.EtendoSQLToCSVTool.convert_json_to_csv")
    @patch("os.path.getsize")
    def test_successful_execution(
        self,
        mock_getsize,
        mock_convert,
        mock_execute,
        setup_tool,
        sample_json_data,
        sample_webhook_url,
        sample_sql_query,
    ):
        """Test successful tool execution."""
        # Setup mocks
        mock_execute.return_value = sample_json_data
        mock_convert.return_value = "/tmp/test_output.csv"
        mock_getsize.return_value = 1024  # 1KB

        # Mock file reading for row count
        with patch("builtins.open", mock_open(read_data="header\nrow1\nrow2\nrow3")):
            input_params = {
                "sql_query": sample_sql_query,
                "webhook_url": sample_webhook_url,
                "auth_token": "test_token",
                "include_headers": True,
            }

            result = setup_tool.run(input_params)

            assert "message" in result
            assert "SQL query executed successfully" in result["message"]
            assert "/tmp/test_output.csv" in result["message"]
            assert "3 rows exported" in result["message"]

    def test_missing_sql_query(self, setup_tool, sample_webhook_url):
        """Test error handling when SQL query is missing."""
        input_params = {"webhook_url": sample_webhook_url}

        result = setup_tool.run(input_params)

        assert "error" in result
        assert "Missing required parameter: 'sql_query'" in result["error"]

    def test_missing_webhook_url(self, setup_tool, sample_sql_query):
        """Test error handling when webhook URL is missing."""
        input_params = {"sql_query": sample_sql_query}

        result = setup_tool.run(input_params)

        assert "error" in result
        assert "Missing required parameter: 'webhook_url'" in result["error"]

    def test_invalid_sql_query(self, setup_tool, sample_webhook_url):
        """Test error handling for invalid SQL queries."""
        input_params = {
            "sql_query": "DROP TABLE users",
            "webhook_url": sample_webhook_url,
        }

        result = setup_tool.run(input_params)

        assert "error" in result
        assert "Invalid SQL query" in result["error"]

    @patch("tools.EtendoSQLToCSVTool.execute_sql_query")
    def test_webhook_execution_error(
        self, mock_execute, setup_tool, sample_webhook_url, sample_sql_query
    ):
        """Test error handling when webhook execution fails."""
        mock_execute.side_effect = requests.RequestException("Connection failed")

        input_params = {
            "sql_query": sample_sql_query,
            "webhook_url": sample_webhook_url,
        }

        result = setup_tool.run(input_params)

        assert "error" in result
        assert "Failed to execute SQL query" in result["error"]

    @patch("tools.EtendoSQLToCSVTool.execute_sql_query")
    @patch("tools.EtendoSQLToCSVTool.convert_json_to_csv")
    def test_csv_conversion_error(
        self,
        mock_convert,
        mock_execute,
        setup_tool,
        sample_json_data,
        sample_webhook_url,
        sample_sql_query,
    ):
        """Test error handling when CSV conversion fails."""
        mock_execute.return_value = sample_json_data
        mock_convert.side_effect = ValueError("Conversion failed")

        input_params = {
            "sql_query": sample_sql_query,
            "webhook_url": sample_webhook_url,
        }

        result = setup_tool.run(input_params)

        assert "error" in result
        assert "Failed to convert result to CSV" in result["error"]

    @patch("tools.EtendoSQLToCSVTool.execute_sql_query")
    @patch("tools.EtendoSQLToCSVTool.convert_json_to_csv")
    @patch("tempfile.gettempdir")
    @patch("os.getpid")
    def test_auto_generated_output_file(
        self,
        mock_getpid,
        mock_gettempdir,
        mock_convert,
        mock_execute,
        setup_tool,
        sample_json_data,
        sample_webhook_url,
        sample_sql_query,
    ):
        """Test automatic output file generation."""
        # Setup mocks
        mock_execute.return_value = sample_json_data
        mock_gettempdir.return_value = "/tmp"
        mock_getpid.return_value = 12345
        expected_path = "/tmp/etendo_query_result_12345.csv"
        mock_convert.return_value = expected_path

        # Mock file operations
        with patch("os.path.getsize", return_value=2048), patch(
            "builtins.open", mock_open(read_data="header\nrow1\nrow2")
        ):
            input_params = {
                "sql_query": sample_sql_query,
                "webhook_url": sample_webhook_url,
            }

            result = setup_tool.run(input_params)

            assert "message" in result
            assert expected_path in result["message"]
