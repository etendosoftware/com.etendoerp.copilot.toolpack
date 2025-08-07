"""
EtendoSQLToCSVTool for Etendo Copilot Toolpack

This tool executes SQL queries in Etendo using the SQLExec webhook,
downloads the JSON result, and converts it to CSV format.

Author: Etendo Software
Version: 1.0
"""

import csv
import datetime
import json
import os
import tempfile
from typing import Dict, Optional, Type

import requests

from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import (
    ToolOutput,
    ToolOutputError,
    ToolOutputMessage,
    ToolWrapper,
)


class EtendoSQLToCSVToolInput(ToolInput):
    """
    Input schema for the EtendoSQLToCSVTool.

    This class defines the expected input parameters for SQL execution and CSV conversion
    using the Etendo SQLExec webhook.

    Attributes:
        sql_query (str): SQL query to execute in Etendo (must be SELECT with table aliases)
        webhook_url (str): URL of the SQLExec webhook endpoint
        auth_token (Optional[str]): Authentication token for the webhook
        output_file (Optional[str]): Path where to save the CSV file (optional)
        include_headers (bool): Whether to include column headers in CSV (default: True)

    Note:
        The SQL query must follow Etendo's security requirements:
        - Only SELECT statements are allowed
        - All tables must have aliases
        - Tables must be accessible to the current user
        - Security filters will be automatically applied
    """

    sql_query: str = ToolField(
        description="SQL SELECT query to execute in Etendo database. All tables must have aliases (e.g., 'SELECT u.name FROM ad_user u')."
    )
    webhook_url: str = ToolField(
        description="URL of the Etendo SQLExec webhook endpoint."
    )
    auth_token: Optional[str] = ToolField(
        default=None,
        description="Authentication token for webhook access (if required).",
    )
    output_file: Optional[str] = ToolField(
        default=None,
        description="Path where to save the CSV file. If not provided, a file will be created in a temporary 'etendo_sql_exports' folder.",
    )
    include_headers: bool = ToolField(
        default=True, description="Whether to include column headers in the CSV output."
    )


def execute_sql_query(
    webhook_url: str, sql_query: str, auth_token: Optional[str] = None
) -> Dict:
    """
    Execute SQL query using Etendo SQLExec webhook.

    Args:
        webhook_url (str): URL of the SQLExec webhook endpoint
        sql_query (str): SQL query to execute
        auth_token (Optional[str]): Authentication token if required

    Returns:
        Dict: JSON response from the webhook

    Raises:
        requests.RequestException: If the HTTP request fails
        ValueError: If the response is not valid JSON
    """
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    # Add authentication header if token is provided
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    payload = {"Query": sql_query}

    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise requests.RequestException(f"Failed to execute SQL query: {str(e)}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from webhook: {str(e)}")


def convert_json_to_csv(
    json_data: Dict, output_file: str, include_headers: bool = True
) -> str:
    """
    Convert JSON data from Etendo SQLExec webhook to CSV format.

    The webhook returns data in this format:
    {
        "queryExecuted": "SELECT ...",
        "columns": ["col1", "col2", "col3"],
        "data": [["val1", "val2", "val3"], ["val4", "val5", "val6"]]
    }

    Args:
        json_data (Dict): JSON data from the SQLExec webhook
        output_file (str): Path where to save the CSV file
        include_headers (bool): Whether to include column headers

    Returns:
        str: Path to the created CSV file

    Raises:
        ValueError: If JSON data format is invalid
        IOError: If file writing fails
    """
    try:
        # Extract columns and data from the Etendo webhook response format
        if "columns" not in json_data or "data" not in json_data:
            raise ValueError(
                "Invalid webhook response format. Expected 'columns' and 'data' fields."
            )

        columns = json_data["columns"]
        data_rows = json_data["data"]

        # Parse columns if it's a JSON string
        if isinstance(columns, str):
            columns = json.loads(columns)

        # Parse data if it's a JSON string
        if isinstance(data_rows, str):
            data_rows = json.loads(data_rows)

        if not data_rows:
            raise ValueError("No data returned from SQL query.")

        # Verify that columns is a list
        if not isinstance(columns, list):
            raise ValueError("Expected 'columns' to be a list of column names.")

        # Verify that data is a list of lists
        if not isinstance(data_rows, list) or (
            data_rows and not isinstance(data_rows[0], list)
        ):
            raise ValueError("Expected 'data' to be a list of lists (rows).")

        # Write CSV file
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write headers if requested
            if include_headers:
                writer.writerow(columns)

            # Write data rows
            writer.writerows(data_rows)

        return output_file

    except (IOError, OSError) as e:
        raise IOError(f"Failed to write CSV file: {str(e)}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON data: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to convert JSON to CSV: {str(e)}")


def validate_sql_query(sql_query: str) -> bool:
    """
    Validate SQL query for Etendo SQLExec webhook compatibility and security.

    Based on the Etendo SQLExec webhook requirements:
    - Only SELECT statements are allowed
    - All tables must have aliases
    - No dangerous keywords permitted

    Args:
        sql_query (str): SQL query to validate

    Returns:
        bool: True if query appears safe and compatible, False otherwise
    """
    # Convert to lowercase for checking
    query_lower = sql_query.lower().strip()

    # Block potentially dangerous operations
    dangerous_keywords = [
        "drop",
        "delete",
        "truncate",
        "alter",
        "create",
        "insert",
        "update",
        "grant",
        "revoke",
        "exec",
        "execute",
        "sp_",
        "xp_",
    ]

    for keyword in dangerous_keywords:
        if keyword in query_lower:
            return False

    # Must start with SELECT
    if not query_lower.startswith("select"):
        return False

    # Basic check for table aliases (this is enforced by the Java webhook)
    # The Java code validates that all tables have aliases, so we inform the user
    if (
        " from " in query_lower
        and " as " not in query_lower
        and not any(
            c.isalpha() and query_lower[i + 1 : i + 2].isspace()
            for i, c in enumerate(query_lower)
            if i < len(query_lower) - 1
        )
    ):
        # This is a basic check - the real validation happens in the Java webhook
        pass

    return True


class EtendoSQLToCSVTool(ToolWrapper):
    """
    A tool for executing SQL queries in Etendo and converting results to CSV.

    This tool connects to Etendo using the SQLExec webhook, executes SQL queries,
    and converts the JSON results to CSV format for easy data analysis and export.

    The tool includes basic SQL validation to prevent dangerous operations and
    only allows SELECT queries for security reasons.

    Supported Operations:
        - Execute SELECT queries in Etendo database
        - Convert JSON results to CSV format
        - Save CSV to specified location or temporary 'etendo_sql_exports' folder
        - Include/exclude column headers in output
        - Automatic timestamp-based file naming for temporary files

    Security Features:
        - SQL injection prevention through query validation
        - Only SELECT statements allowed
        - Authentication token support

    Example:
        >>> tool = EtendoSQLToCSVTool()
        >>> params = {
        ...     "sql_query": "SELECT u.name, u.email FROM ad_user u WHERE u.isactive = 'Y'",
        ...     "webhook_url": "https://your-etendo.com/webhooks/execsql",
        ...     "auth_token": "your_token_here"
        ... }
        >>> result = tool.run(params)
    """

    name: str = "EtendoSQLToCSVTool"
    description: str = (
        "Tool to execute SQL queries in Etendo using the SQLExec webhook and convert results to CSV. "
        "This tool connects to Etendo's database through the SQLExec webhook, executes SELECT queries, "
        "and downloads the JSON result converted to CSV format. "
        "REQUIREMENTS: Only SELECT queries are allowed, all tables must have aliases (e.g., 'SELECT u.name FROM ad_user u'), "
        "and tables must be accessible to the current user. Security filters are automatically applied by Etendo. "
        "Parameters: sql_query (required), webhook_url (required), auth_token (optional), "
        "output_file (optional), include_headers (optional, default: true)."
    )
    args_schema: Type[ToolInput] = EtendoSQLToCSVToolInput
    return_direct: bool = False

    def run(self, input_params: Dict = None, *args, **kwargs) -> ToolOutput:
        """
        Execute SQL query and convert result to CSV.

        Args:
            input_params (Dict): Input parameters containing SQL query and configuration

        Returns:
            ToolOutput: Success message with CSV file path or error message
        """
        try:
            # Extract input parameters
            sql_query = input_params.get("sql_query")
            webhook_url = input_params.get("webhook_url")
            auth_token = input_params.get("auth_token")
            output_file = input_params.get("output_file")
            include_headers = input_params.get("include_headers", True)

            # Validate required parameters
            if not sql_query:
                return ToolOutputError(error="Missing required parameter: 'sql_query'")

            if not webhook_url:
                return ToolOutputError(
                    error="Missing required parameter: 'webhook_url'"
                )

            # Validate SQL query for security
            if not validate_sql_query(sql_query):
                return ToolOutputError(
                    error="Invalid SQL query. Only SELECT queries are allowed and no dangerous keywords permitted. "
                    "Note: Etendo also requires all tables to have aliases (e.g., 'FROM ad_user u')."
                )

            # Generate output file path if not provided
            if not output_file:
                # Create a temporary directory for Etendo SQL exports
                temp_base_dir = tempfile.gettempdir()
                etendo_temp_dir = os.path.join(temp_base_dir, "etendo_sql_exports")

                # Create the directory if it doesn't exist
                os.makedirs(etendo_temp_dir, exist_ok=True)

                # Generate unique filename with timestamp
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"etendo_query_{timestamp}_{os.getpid()}.csv"
                output_file = os.path.join(etendo_temp_dir, filename)

            # Execute SQL query
            try:
                json_result = execute_sql_query(webhook_url, sql_query, auth_token)
            except requests.RequestException as e:
                return ToolOutputError(error=f"Failed to execute SQL query: {str(e)}")
            except ValueError as e:
                return ToolOutputError(error=f"Invalid response from webhook: {str(e)}")

            # Convert JSON to CSV
            try:
                csv_file_path = convert_json_to_csv(
                    json_result, output_file, include_headers
                )
            except (ValueError, IOError) as e:
                return ToolOutputError(
                    error=f"Failed to convert result to CSV: {str(e)}"
                )

            # Get file size for reporting
            try:
                file_size = os.path.getsize(csv_file_path)
                file_size_mb = file_size / (1024 * 1024)
            except OSError:
                file_size_mb = 0

            # Count rows in result
            try:
                with open(csv_file_path, "r", encoding="utf-8") as f:
                    row_count = sum(1 for _ in f)
                    if include_headers and row_count > 0:
                        row_count -= 1  # Subtract header row
            except IOError:
                row_count = 0

            return ToolOutputMessage(
                message=f"✅ SQL query executed successfully!\n"
                f"📊 Result: {row_count} rows exported\n"
                f"📁 CSV file saved at: {csv_file_path}\n"
                f"� Temporary folder: {os.path.dirname(csv_file_path)}\n"
                f"�📏 File size: {file_size_mb:.2f} MB\n"
                f"🔍 Query: {sql_query[:100]}{'...' if len(sql_query) > 100 else ''}"
            )

        except Exception as e:
            return ToolOutputError(error=f"EtendoSQLToCSVTool error: {str(e)}")
