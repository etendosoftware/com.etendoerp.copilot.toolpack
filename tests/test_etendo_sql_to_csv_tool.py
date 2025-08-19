"""
Test suite for EtendoSQLToCSVTool

This module contains comprehensive unit tests for the EtendoSQLToCSVTool class,
covering SQL query execution, JSON to CSV conversion, and error handling scenarios.
"""

import os
import tempfile
import uuid
from unittest.mock import mock_open, patch

import pytest

from tools.EtendoSQLToCSVTool import (
    EtendoSQLToCSVTool,
    EtendoSQLToCSVToolInput,
    convert_json_to_csv,
    execute_sql_query,
    validate_sql_query,
)


def create_test_csv_path(filename=None):
    """
    Create a test CSV file path in a secure temporary directory.

    Args:
        filename (str, optional): Custom filename. If None, generates a unique name.

    Returns:
        str: Full path to the test CSV file
    """
    # Create a secure temporary directory specific to this process and user
    base_temp_dir = tempfile.gettempdir()
    test_dir = os.path.join(
        base_temp_dir,
        f"etendo_sql_test_{os.getuid() if hasattr(os, 'getuid') else 'user'}_{os.getpid()}",
    )

    # Create directory with secure permissions (only readable/writable by owner)
    os.makedirs(test_dir, mode=0o700, exist_ok=True)

    if filename is None:
        filename = f"test_{uuid.uuid4().hex[:8]}.csv"

    return os.path.join(test_dir, filename)


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
        # Use secure temporary path instead of hardcoded /tmp path
        secure_output_file = create_test_csv_path("test_valid_input.csv")

        input_data = EtendoSQLToCSVToolInput(
            sql_query="SELECT u.name FROM ad_user u",
            output_file=secure_output_file,
            include_headers=True,
        )
        assert input_data.sql_query == "SELECT u.name FROM ad_user u"
        assert input_data.output_file == secure_output_file
        assert input_data.include_headers is True

    def test_minimal_input(self):
        """Test minimal required input."""
        input_data = EtendoSQLToCSVToolInput(sql_query="SELECT u.id FROM ad_user u")
        assert input_data.sql_query == "SELECT u.id FROM ad_user u"
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

    @patch("tools.EtendoSQLToCSVTool.get_etendo_host")
    @patch("tools.EtendoSQLToCSVTool.get_etendo_token")
    @patch("tools.EtendoSQLToCSVTool.call_webhook")
    def test_successful_query_execution(
        self,
        mock_call_webhook,
        mock_get_token,
        mock_get_host,
        sample_sql_query,
        sample_json_data,
    ):
        """Test successful SQL query execution using Etendo utils."""
        # Setup mocks for Etendo utilities
        mock_get_token.return_value = "test_token"
        mock_get_host.return_value = "https://test-etendo.com"
        mock_call_webhook.return_value = sample_json_data

        result = execute_sql_query(sample_sql_query)

        assert result == sample_json_data
        mock_call_webhook.assert_called_once_with(
            "test_token",
            {"Query": sample_sql_query, "Mode": "EXECUTE_QUERY"},
            "https://test-etendo.com",
            "DBQueryExec",
        )

    @patch("tools.EtendoSQLToCSVTool.get_etendo_host")
    @patch("tools.EtendoSQLToCSVTool.get_etendo_token")
    @patch("tools.EtendoSQLToCSVTool.call_webhook")
    def test_webhook_error_handling(
        self, mock_call_webhook, mock_get_token, mock_get_host, sample_sql_query
    ):
        """Test handling of webhook errors."""
        # Setup mocks
        mock_get_token.return_value = "test_token"
        mock_get_host.return_value = "https://test-etendo.com"
        mock_call_webhook.return_value = {"error": "Database connection failed"}

        from tools.EtendoSQLToCSVTool import WebhookError

        with pytest.raises(WebhookError) as exc_info:
            execute_sql_query(sample_sql_query)

        assert "Webhook error: Database connection failed" in str(exc_info.value)


class TestConvertJSONToCSV:
    """Test cases for JSON to CSV conversion."""

    def test_successful_conversion_with_data_field(self, sample_json_data):
        """Test successful conversion with Etendo webhook response format."""
        temp_path = create_test_csv_path()

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
            if os.path.exists(temp_path):
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

        temp_path = create_test_csv_path()

        try:
            result_path = convert_json_to_csv(json_data, temp_path, True)
            assert result_path == temp_path

            # Verify CSV content
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "product,price" in content
                assert "Laptop" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_conversion_without_headers(self, sample_json_data):
        """Test CSV conversion without headers."""
        temp_path = create_test_csv_path()

        try:
            convert_json_to_csv(sample_json_data, temp_path, False)

            # Verify CSV content has no headers
            with open(temp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                assert not lines[0].startswith("id,name,email")
                assert "John Doe" in lines[0]
        finally:
            if os.path.exists(temp_path):
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

        temp_path = create_test_csv_path()

        try:
            convert_json_to_csv(json_data, temp_path, True)

            # Verify CSV content
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
                assert "status,count" in content
                assert "active,5" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_conversion_empty_data(self):
        """Test conversion with empty data."""
        json_data = {"columns": ["id", "name"], "data": []}

        temp_path = create_test_csv_path()

        try:
            from tools.EtendoSQLToCSVTool import CSVConversionError

            with pytest.raises(CSVConversionError) as exc_info:
                convert_json_to_csv(json_data, temp_path, True)
            assert "No data returned from SQL query" in str(exc_info.value)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_conversion_invalid_format(self):
        """Test conversion with invalid JSON format."""
        json_data = {"invalid": "format"}

        temp_path = create_test_csv_path()

        try:
            from tools.EtendoSQLToCSVTool import CSVConversionError

            with pytest.raises(CSVConversionError) as exc_info:
                convert_json_to_csv(json_data, temp_path, True)
            assert "Invalid webhook response format" in str(exc_info.value)
        finally:
            if os.path.exists(temp_path):
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
        sample_sql_query,
    ):
        """Test successful tool execution."""
        # Setup mocks
        mock_execute.return_value = sample_json_data
        csv_path = create_test_csv_path()
        mock_convert.return_value = csv_path
        mock_getsize.return_value = 1024  # 1KB

        # Mock file reading for row count
        with patch("builtins.open", mock_open(read_data="header\nrow1\nrow2\nrow3")):
            input_params = {
                "sql_query": sample_sql_query,
                "include_headers": True,
            }

            result = setup_tool.run(input_params)

            assert "message" in result
            assert "SQL query executed successfully" in result["message"]
            assert csv_path in result["message"]
            assert "3 rows exported" in result["message"]

    def test_missing_sql_query(self, setup_tool):
        """Test error handling when SQL query is missing."""
        input_params = {}

        result = setup_tool.run(input_params)

        assert "error" in result
        assert "Missing required parameter: 'sql_query'" in result["error"]

    def test_invalid_sql_query(self, setup_tool):
        """Test error handling for invalid SQL queries."""
        input_params = {
            "sql_query": "DROP TABLE users",
        }

        result = setup_tool.run(input_params)

        assert "error" in result
        assert "Invalid SQL query" in result["error"]

    @patch("tools.EtendoSQLToCSVTool.execute_sql_query")
    def test_query_execution_error(self, mock_execute, setup_tool, sample_sql_query):
        """Test error handling when SQL execution fails."""
        from tools.EtendoSQLToCSVTool import SQLQueryError

        mock_execute.side_effect = SQLQueryError("Database connection failed")

        input_params = {
            "sql_query": sample_sql_query,
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
        sample_sql_query,
    ):
        """Test error handling when CSV conversion fails."""
        mock_execute.return_value = sample_json_data
        mock_convert.side_effect = ValueError("Conversion failed")

        input_params = {
            "sql_query": sample_sql_query,
        }

        result = setup_tool.run(input_params)

        assert "error" in result
        assert "Failed to convert result to CSV" in result["error"]
