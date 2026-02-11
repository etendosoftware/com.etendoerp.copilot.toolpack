import csv
import os
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Type

import pandas as pd
from requests import Response

from copilot.core.utils.etendo_utils import (
    get_etendo_host,
    get_etendo_token,
    request_to_etendo,
    simple_request_to_etendo,
)
from copilot.core.exceptions import ToolException
from copilot.core.threadcontext import ThreadContext
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper
from copilot.baseutils.logging_envvar import is_docker

TASK_TYPE_COPILOT = "A83E397389DB42559B2D7719A442168F"

TASK_STATUS_PENDING = "D0FCC72902F84486A890B70C1EB10C9C"


class TaskCreatorToolInput(ToolInput):
    question: str = ToolField(
        title="Question",
        description="""Question/request for the Task. The tool will create a task for
        each extracted file or row. The question will be used as the task description,
        for  the item, so is recommended that be a singularized question/request.
        For example, if the file contains a list of products and the main objective is
        to "process" the products, the question should be "Process the "product"."
        """,
    )
    file_path: str = ToolField(
        title="File Path", description="Path to the ZIP, CSV, XLS, or XLSX file."
    )
    group_id: str = ToolField(
        title="Group ID",
        description="ID of the group to which the task belongs. If not provided, the "
        "tool will "
        "create it.",
    )
    groupby: List[str] = ToolField(
        default=[],
        title="Group By",
        description=(
            "Optional list of column names to group rows by when processing CSV/XLS files. "
            "If provided, rows that share the same values for these columns will be sent "
            "as a single task (the task item will be a JSON array string with all rows in the group). "
            "If no grouping is desired, send an empty array []."
        ),
    )
    task_type_id: Optional[str] = ToolField(
        title="Task Type",
        description="ID of the task type. If not provided, the tool use the Copilot's "
        "default task type.",
    )
    status_id: Optional[str] = ToolField(
        title="Status",
        description="ID of the pending status. If not provided, the tool will "
        "create it.",
    )
    agent_id: Optional[str] = ToolField(
        title="Agent ID",
        description="ID of the agent to which the task is assigned. This agent will be"
        " who processes the task. If not provided, the tool will use the current main "
        "assistant's ID.",
    )
    preview: Optional[bool] = ToolField(
        title="Preview",
        description="If true, the tool will return the column names (or file contents for ZIP) instead of creating tasks.",
    )


def send_taskapi_request(
    q: str, task_type, status, agent, group_id, item, host, token
) -> Response:
    """Sends a request to the Etendo API to create a new task with the provided parameters.

    Args:
        q (str): The question or description for the task.
        task_type: The type of the task.
        status: The status of the task.
        agent: The agent assigned to the task.
        group_id: The group ID for the task.
        item: The item data for the task.
        host: The Etendo host URL.
        token: The authentication token.

    Returns:
        Response: The response from the Etendo API.
    """
    payload = {
        "taskType": task_type,
        "status": status,
        "etcopQuestion": q + ":" + item,
        "eTCOPAgent": agent,
        "etcopGroup": group_id,
    }
    response = request_to_etendo(
        "POST", payload, "/sws/com.etendoerp.etendorx.datasource/Task", host, token
    )

    return response


def process_zip(zip_path: str) -> List[str]:
    """Processes a ZIP file by extracting its contents and returning a list of file paths.

    Args:
        zip_path (str): The path to the ZIP file to process.

    Returns:
        List[str]: A list of paths to the extracted files.
    """
    try:
        result = []

        # Determine prefix based on the environment
        prefix = os.getcwd() if not is_docker() else ""
        temp_file_path = Path(f"{prefix}/copilotAttachedFiles/{uuid.uuid4()}")
        temp_file_path.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            members = [
                m for m in zip_ref.infolist() if not m.filename.startswith("__MACOSX/")
            ]
            zip_ref.extractall(temp_file_path, members=[m.filename for m in members])

        # Walk through the extracted files and store their paths
        for root, _, files in os.walk(temp_file_path):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                result.append(full_path)

        return result

    except Exception as e:
        raise ToolException(f"Error processing ZIP file {zip_path}: {str(e)}")


def process_csv(csv_path: str) -> List[str]:
    """Processes a CSV file and returns a list of string representations of each row as a dictionary.

    Args:
        csv_path (str): The path to the CSV file to process.

    Returns:
        List[str]: A list of string representations of rows.
    """
    # Backwards compatible CSV processing without grouping
    try:
        final_result = []
        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)  # Get header row.
            for row_number, row in enumerate(reader, start=2):
                row_data = dict(zip(headers, row))
                final_result.append(str(row_data))
        return final_result
    except Exception as e:
        raise ToolException(f"Error processing CSV file {csv_path}: {str(e)}")


def process_xls(xls_path: str) -> List[str]:
    """Processes an Excel file and returns a list of string representations of each row as a dictionary.

    Args:
        xls_path (str): The path to the Excel file to process.

    Returns:
        List[str]: A list of string representations of rows.
    """
    # Backwards compatible Excel processing without grouping
    try:
        result = []
        df = pd.read_excel(xls_path)
        headers = list(df.columns)
        for index, row in df.iterrows():
            row_data = dict(zip(headers, row))
            result.append(str(row_data))
        return result
    except Exception as e:
        raise ToolException(f"Error processing Excel file {xls_path}: {str(e)}")


def process_csv_grouped(csv_path: str, groupby: List[str]) -> List[str]:
    """Process CSV and group rows by groupby columns. Returns list of JSON-like strings (one per group).

    Args:
        csv_path (str): The path to the CSV file to process.
        groupby (List[str]): List of column names to group by.

    Returns:
        List[str]: A list of JSON strings, each representing a group of rows.
    """
    try:
        import json

        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            headers = reader.fieldnames or []
            # Validate groupby columns exist
            for col in groupby:
                if col not in headers:
                    raise ToolException(
                        f"Group by column '{col}' not found in CSV headers: {headers}"
                    )

            groups = {}
            for row in reader:
                key = tuple(row.get(col, "") for col in groupby)
                groups.setdefault(key, []).append(row)

        # Convert each group to a single item (JSON string)
        result = [json.dumps(rows, ensure_ascii=False) for rows in groups.values()]
        return result
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(
            f"Error processing CSV file {csv_path} with grouping {groupby}: {str(e)}"
        )


def process_xls_grouped(xls_path: str, groupby: List[str]) -> List[str]:
    """Process Excel and group rows by groupby columns. Returns list of JSON-like strings (one per group).

    Args:
        xls_path (str): The path to the Excel file to process.
        groupby (List[str]): List of column names to group by.

    Returns:
        List[str]: A list of JSON strings, each representing a group of rows.
    """
    try:
        import json

        df = pd.read_excel(xls_path, dtype=str)
        df.fillna("", inplace=True)
        headers = list(df.columns)
        for col in groupby:
            if col not in headers:
                raise ToolException(
                    f"Group by column '{col}' not found in Excel headers: {headers}"
                )

        grouped = df.groupby(groupby, dropna=False)
        result = []
        for _, group_df in grouped:
            # Convert group rows to list of dicts
            rows = group_df.to_dict(orient="records")
            result.append(json.dumps(rows, ensure_ascii=False))
        return result
    except ToolException:
        raise
    except Exception as e:
        raise ToolException(
            f"Error processing Excel file {xls_path} with grouping {groupby}: {str(e)}"
        )


def process_file(file_path: str, groupby: Optional[List[str]] = None) -> List[str]:
    """Processes a file based on its type (ZIP, CSV, XLS/XLSX) and returns a list of items for task creation.

    Args:
        file_path (str): The path to the file to process.
        groupby (Optional[List[str]]): Optional list of columns to group by for CSV/Excel files.

    Returns:
        List[str]: A list of items (file paths or row strings) for task creation.
    """
    if not file_path or not os.path.exists(file_path):
        raise ToolException(f"File not found: {file_path}")

    if file_path.endswith(".zip"):
        items = process_zip(file_path)
    elif file_path.endswith(".csv"):
        if groupby:
            items = process_csv_grouped(file_path, groupby)
        else:
            items = process_csv(file_path)
    elif file_path.endswith((".xls", ".xlsx")):
        if groupby:
            items = process_xls_grouped(file_path, groupby)
        else:
            items = process_xls(file_path)
    else:
        items = [file_path]
    return items


def preview_file(file_path: str) -> Dict:
    """Return a preview of the file: for CSV/XLSX returns list of columns; for ZIP returns list of contained files; otherwise returns file info.

    Args:
        file_path (str): The path to the file to preview.

    Returns:
        Dict: A dictionary containing preview information (type, columns/files, etc.).
    """
    if not file_path or not os.path.exists(file_path):
        raise ToolException(f"File not found: {file_path}")

    if file_path.endswith(".zip"):
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                members = [m for m in z.namelist() if not m.startswith("__MACOSX/")]
            return {"type": "zip", "files": members}
        except Exception as e:
            raise ToolException(f"Error previewing ZIP file {file_path}: {str(e)}")
    elif file_path.endswith(".csv"):
        try:
            with open(file_path, newline="", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                headers = next(reader)
            return {"type": "csv", "columns": headers}
        except Exception as e:
            raise ToolException(f"Error previewing CSV file {file_path}: {str(e)}")
    elif file_path.endswith((".xls", ".xlsx")):
        try:
            df = pd.read_excel(file_path, nrows=0)
            return {"type": "excel", "columns": list(df.columns)}
        except Exception as e:
            raise ToolException(f"Error previewing Excel file {file_path}: {str(e)}")
    else:
        return {"type": "file", "name": os.path.basename(file_path)}


def read_record(task_types):
    """Extracts the records from the task types response data.

    Args:
        task_types: The response data containing task types.

    Returns:
        list: A list of records from the response.
    """
    try:
        if not task_types:
            return []
        response = task_types.get("response")
        if not response:
            return []
        records_arr = response.get("data")
        return records_arr or []
    except Exception:
        return []


def get_or_create_task_type(name):
    """Retrieves or creates a task type with the given name in the Etendo system.

    Args:
        name: The name of the task type to retrieve or create.

    Returns:
        str: The ID of the task type.
    """
    response = simple_request_to_etendo(
        "GET",
        {},
        "/sws/com.etendoerp.etendorx.datasource/TaskType?q=name==Copilot"
        "&_startRow=0&_endRow=10",
    )
    tt_id = None
    if response.status_code == 200:
        task_types = response.json()
        if task_types:
            record = read_record(task_types)
            if len(record) > 0:
                tt_id = record[0].get("id")
    if response.status_code == 500:
        raise ToolException(
            "Error retrieving TaskType. Check if the user has permission to view TaskTypes."
        )
    if not tt_id:
        response = simple_request_to_etendo(
            "POST", {"name": name}, "/sws/com.etendoerp.etendorx.datasource/TaskType"
        )
        record = read_record(response.json())
        tt_id = record[0].get("id")
    return tt_id


def get_or_create_status(param):
    """Retrieves or creates a task status with the given name in the Etendo system.

    Args:
        param: The name of the status to retrieve or create.

    Returns:
        str: The ID of the task status.
    """
    response = simple_request_to_etendo(
        "GET",
        {},
        "/sws/com.etendoerp.etendorx.datasource/TaskStatus?q=name==Pending&_startRow=0&_endRow=10",
    )
    status_id = None
    if response.status_code == 200:
        statuses = response.json()
        records = read_record(statuses)
        if statuses and len(records) > 0 and records[0].get("id"):
            status_id = read_record(statuses)[0].get("id")
    if not status_id:
        response = simple_request_to_etendo(
            "POST", {"name": param}, "/sws/com.etendoerp.etendorx.datasource/TaskStatus"
        )
        status_id = read_record(response.json())[0].get("id")
    return status_id


def read_groupby_param_values(groupby_param):
    """Normalizes the groupby parameter into a list of column names.

    Args:
        groupby_param: The groupby parameter, can be a list or comma-separated string.

    Returns:
        list or None: A list of column names or None if not provided.
    """
    # Normalize groupby: accept list or comma-separated string
    groupby = None
    if groupby_param:
        if isinstance(groupby_param, list):
            groupby = [str(c).strip() for c in groupby_param if str(c).strip()]
        elif isinstance(groupby_param, str):
            groupby = [c.strip() for c in groupby_param.split(",") if c.strip()]
        else:
            # Unexpected type
            raise ToolException(
                "Invalid 'groupby' parameter. Provide a list or a comma-separated string of column names."
            )
    return groupby


class TaskCreatorTool(ToolWrapper):
    name: str = "TaskCreatorTool"  # SearchKey must match the class name.
    description: str = (
        "Processes a ZIP, CSV, or Excel file and creates a task for each extracted file or row. "
        "For ZIP files, each uncompressed file's full path is added to the question/request. "
        "For CSV or Excel files, the header row is skipped and each subsequent row task includes "
        "the header and the row data. If the file format is unsupported, a task is created with the file path."
    )
    args_schema: Type[ToolInput] = TaskCreatorToolInput

    def run(self, input_params: Dict, *args, **kwargs) -> Dict:
        """Executes the task creation process based on the input parameters.

        Args:
            input_params (Dict): The input parameters for task creation.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Dict: A dictionary containing the result of the task creation process.
        """
        try:
            # Retrieve parameters from the input.
            question = input_params.get("question")
            file_path = input_params.get("file_path")
            task_type = input_params.get("task_type_id")
            status = input_params.get("status_id")
            group_id = input_params.get("group_id")
            agent = input_params.get("agent_id")
            groupby_param = input_params.get("groupby")
            preview_param = input_params.get("preview")

            groupby = read_groupby_param_values(groupby_param)

            if not task_type or task_type == "":
                task_type = TASK_TYPE_COPILOT
            if not status or status == "":
                status = TASK_STATUS_PENDING
            if not group_id or group_id == "":
                group_id = ThreadContext.get_data("conversation_id") or str(
                    uuid.uuid4()
                )
            if not agent or agent == "":
                agent = ThreadContext.get_data("assistant_id")
            if not file_path:
                raise ToolException("'file_path' parameter is required.")

            # Ensure question is a string
            question = str(question) if question is not None else ""

            # If preview requested, return columns or zip contents instead of creating tasks
            if preview_param:
                preview_result = preview_file(file_path)
                return {"preview": preview_result}

            items = process_file(file_path, groupby)
            responses = []

            import concurrent.futures

            host = get_etendo_host()
            token = get_etendo_token()

            def process_item(i):
                return send_taskapi_request(
                    question,
                    task_type,
                    status,
                    agent,
                    group_id,
                    i,
                    host,
                    token,
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(process_item, item) for item in items]
                for future in concurrent.futures.as_completed(futures):
                    responses.append(future.result())

            print(responses)
            return {
                "message": f"Bulk Task creation process completed, the tasks from this batch group has the group id: {group_id}"
            }
        except ToolException as e:
            return {"error": f"Tool error creating tasks: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error creating tasks: {str(e)}"}
