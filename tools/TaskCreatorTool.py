import csv
import os
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Type

import pandas as pd
from requests import Response

from core.utils.etendo_utils import (
    get_etendo_host,
    get_etendo_token,
    request_to_etendo,
    simple_request_to_etendo,
)
from copilot.core.exceptions import ToolException
from copilot.core.threadcontext import ThreadContext
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper
from baseutils.logging_envvar import is_docker

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


def send_taskapi_request(
    q: str, task_type, status, agent, group_id, item, host, token
) -> Response:
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


def process_file(file_path: str) -> List[str]:
    if not os.path.exists(file_path):
        raise ToolException(f"File not found: {file_path}")
    if file_path.endswith(".zip"):
        items = process_zip(file_path)
    elif file_path.endswith(".csv"):
        items = process_csv(file_path)
    elif file_path.endswith((".xls", ".xlsx")):
        items = process_xls(file_path)
    else:
        items = [file_path]
    return items


def read_record(task_types):
    try:
        records_arr = task_types.get("response").get("data")
        return records_arr
    except Exception:
        return None


def get_or_create_task_type(name):
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
        try:
            # Retrieve parameters from the input.
            question = input_params.get("question")
            file_path = input_params.get("file_path")
            task_type = input_params.get("task_type_id")
            status = input_params.get("status_id")
            group_id = input_params.get("group_id")
            agent = input_params.get("agent_id")

            if not task_type or task_type == "":
                task_type = TASK_TYPE_COPILOT
            if not status or status == "":
                status = TASK_STATUS_PENDING
            if not group_id or group_id == "":
                group_id = ThreadContext.get_data("conversation_id")
            if not agent or agent == "":
                agent = ThreadContext.get_data("assistant_id")
            items = process_file(file_path)
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
                "message": "Bulk Task creation process completed, the tasks from "
                "this batch group has the group id: " + group_id
            }
        except Exception as e:
            raise ToolException(f"Error creating tasks: {str(e)}")
