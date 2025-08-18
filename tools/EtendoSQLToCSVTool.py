"""
EtendoSQLToCSVTool for Etendo Copilot Toolpack

This tool executes SQL queries in Etendo using the SQLExec webhook,
downloads the JSON result, and converts it to CSV format.

Author: Etendo Software
Version: 1.0
"""

import csv
import json
import os
import tempfile
from typing import Dict, Optional, Type

from copilot.core.etendo_utils import call_webhook, get_etendo_host, get_etendo_token
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import (
    ToolOutput,
    ToolOutputError,
    ToolOutputMessage,
    ToolWrapper,
)


class WebhookError(Exception):
    """Custom exception for webhook-related errors"""

    pass


class SQLQueryError(Exception):
    """Custom exception for SQL query execution errors"""

    pass


class CSVConversionError(Exception):
    """Custom exception for CSV conversion errors"""

    pass


class EtendoSQLToCSVToolInput(ToolInput):
    """
    Input schema for the EtendoSQLToCSVTool.

    This class defines the expected input parameters for SQL execution and CSV conversion
    using the Etendo DBQueryExec webhook through the call_webhook utility.

    Attributes:
        sql_query (str): SQL query to execute in Etendo (must be SELECT with table aliases)
        output_file (Optional[str]): Path where to save the CSV file (optional)
        include_headers (bool): Whether to include column headers in CSV (default: True)

    Note:
        The SQL query must follow Etendo's security requirements:
        - Only SELECT statements are allowed
        - All tables must have aliases
        - Tables must be accessible to the current user
        - Security filters will be automatically applied

        Authentication and Etendo host are handled automatically through the copilot context.
    """

    sql_query: str = ToolField(
        description="SQL SELECT query to execute in Etendo database. All tables must have aliases (e.g., 'SELECT u.name FROM ad_user u')."
    )
    output_file: Optional[str] = ToolField(
        default=None,
        description="Path where to save the CSV file. If not provided, a temporary file will be created.",
    )
    include_headers: bool = ToolField(
        default=True, description="Whether to include column headers in the CSV output."
    )


def execute_sql_query(sql_query: str) -> Dict:
    """
    Execute SQL query using Etendo DBQueryExec webhook through call_webhook utility.

    Args:
        sql_query (str): SQL query to execute

    Returns:
        Dict: JSON response from the webhook

    Raises:
        WebhookError: If the webhook call fails or returns an error
        SQLQueryError: If there's an error with the SQL query execution
    """
    try:
        # Get authentication token and Etendo host automatically
        access_token = get_etendo_token()
        etendo_host = get_etendo_host()

        # Prepare the payload for the DBQueryExec webhook
        body_params = {"Query": sql_query, "Mode": "EXECUTE_QUERY"}

        # Call the webhook using the utility function
        result = call_webhook(access_token, body_params, etendo_host, "DBQueryExec")

        # Check if the webhook returned an error
        if isinstance(result, dict) and "error" in result:
            raise WebhookError(f"Webhook error: {result['error']}")

        return result

    except WebhookError:
        raise
    except Exception as e:
        raise SQLQueryError(f"Failed to execute SQL query: {str(e)}")


def convert_json_to_csv(
    json_data: Dict, output_file: str, include_headers: bool = True
) -> str:
    """
    Convert JSON data from Etendo DBQueryExec webhook to CSV format.

    The webhook returns data in this format:
    {
        "queryExecuted": "SELECT ...",
        "columns": ["col1", "col2", "col3"],
        "data": [["val1", "val2", "val3"], ["val4", "val5", "val6"]]
    }

    Args:
        json_data (Dict): JSON data from the DBQueryExec webhook
        output_file (str): Path where to save the CSV file
        include_headers (bool): Whether to include column headers

    Returns:
        str: Path to the created CSV file

    Raises:
        ValueError: If JSON data format is invalid
        IOError: If file writing fails
        CSVConversionError: If there's an error during CSV conversion
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
        raise CSVConversionError(f"Failed to convert JSON to CSV: {str(e)}")


def validate_sql_query(sql_query: str) -> bool:
    """
    Validate SQL query for Etendo DBQueryExec webhook compatibility and security.

    Based on the Etendo DBQueryExec webhook requirements:
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

    This tool connects to Etendo using the DBQueryExec webhook through the call_webhook utility,
    executes SQL queries, and converts the JSON results to CSV format for easy data analysis and export.

    The tool automatically handles authentication and Etendo host configuration through the copilot context,
    making it much simpler to use than manually configuring webhook URLs and tokens.

    The tool includes basic SQL validation to prevent dangerous operations and
    only allows SELECT queries for security reasons.

    Supported Operations:
        - Execute SELECT queries in Etendo database
        - Convert JSON results to CSV format
        - Save CSV to specified location or temporary file
        - Include/exclude column headers in output

    Security Features:
        - SQL injection prevention through query validation
        - Only SELECT statements allowed
        - Automatic authentication through copilot context

    Example:
        >>> tool = EtendoSQLToCSVTool()
        >>> params = {
        ...     "sql_query": "SELECT u.name, u.email FROM ad_user u WHERE u.isactive = 'Y'"
        ... }
        >>> result = tool.run(params)
    """

    name: str = "EtendoSQLToCSVTool"
    description: str = (
        "Tool to execute SQL queries in Etendo using the DBQueryExec webhook and convert results to CSV. "
        "This tool connects to Etendo's database through the DBQueryExec webhook, executes SELECT queries, "
        "and downloads the JSON result converted to CSV format. "
        "REQUIREMENTS: Only SELECT queries are allowed, all tables must have aliases (e.g., 'SELECT u.name FROM ad_user u'), "
        "and tables must be accessible to the current user. Security filters are automatically applied by Etendo. "
        "Authentication and Etendo host are handled automatically through the copilot context. "
        "Parameters: sql_query (required), output_file (optional), include_headers (optional, default: true)."
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
            output_file = input_params.get("output_file")
            include_headers = input_params.get("include_headers", True)

            # Validate required parameters
            if not sql_query:
                return ToolOutputError(error="Missing required parameter: 'sql_query'")

            # Validate SQL query for security
            if not validate_sql_query(sql_query):
                return ToolOutputError(
                    error="Invalid SQL query. Only SELECT queries are allowed and no dangerous keywords permitted. "
                    "Note: Etendo also requires all tables to have aliases (e.g., 'FROM ad_user u')."
                )

            # Generate output file path if not provided
            if not output_file:
                # Create a secure temporary directory for organized CSV exports
                # Use process ID and user ID for uniqueness and security
                base_temp_dir = tempfile.gettempdir()
                export_dir = os.path.join(
                    base_temp_dir,
                    f"etendo_sqlexport_{os.getuid() if hasattr(os, 'getuid') else 'user'}_{os.getpid()}",
                )
                # Create directory with secure permissions (only readable/writable by owner)
                os.makedirs(export_dir, mode=0o700, exist_ok=True)
                output_file = os.path.join(
                    export_dir, f"etendo_query_result_{os.getpid()}.csv"
                )

            # Execute SQL query using the simplified webhook call
            try:
                json_result = execute_sql_query(sql_query)
            except (WebhookError, SQLQueryError) as e:
                return ToolOutputError(error=f"Failed to execute SQL query: {str(e)}")

            # Convert JSON to CSV
            try:
                csv_file_path = convert_json_to_csv(
                    json_result, output_file, include_headers
                )
            except (ValueError, IOError, CSVConversionError) as e:
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
                f"📏 File size: {file_size_mb:.2f} MB\n"
                f"🔍 Query: {sql_query[:100]}{'...' if len(sql_query) > 100 else ''}"
            )

        except Exception as e:
            return ToolOutputError(error=f"EtendoSQLToCSVTool error: {str(e)}")
