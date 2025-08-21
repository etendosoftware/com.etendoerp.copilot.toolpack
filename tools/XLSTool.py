import os
from pathlib import Path
from typing import Dict, Optional, Type

from copilot.core.exceptions import ToolException
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolOutput, ToolOutputError, ToolWrapper
from copilot.baseutils.logging_envvar import copilot_debug


class XLSToolInput(ToolInput):
    path: str = ToolField(description="XLS/CSV file path")
    only_headers: Optional[bool] = ToolField(
        description="Mode to only read the headers of the file", default=False
    )


def process_file(file_path, mode):
    import pandas as pd  # pip install pandas

    # Verifies that the file has an allowed extension
    valid_extensions = [".csv", ".xlsx"]
    file_extension = os.path.splitext(file_path)[1]

    if file_extension not in valid_extensions:
        raise ValueError("The file must have a .csv or .xlsx extension")

    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.max_colwidth", None)
    # load the file according to its extension
    if file_extension == ".csv":
        data = pd.read_csv(file_path)
    elif file_extension == ".xlsx":
        data = pd.read_excel(file_path)

    # Process according to the selected mode
    if mode == "headers":
        return list(data.columns)
    elif mode == "all":
        return data
    else:
        raise ValueError("Mode must be 'headers' or 'all'")


class XLSTool(ToolWrapper):
    """A tool to read an XLS/CSV file and retrieve its content.

    Attributes:
        path (str): The path to the XLS/CSV file.
        mode (str): The mode of reading the file. It can be either 'headers' to only read the headers or 'all' to read
        the entire file content.
    """

    name: str = "XLSTool"
    description: str = "A tool to read an XLS/CSV file and retrieve its content."
    args_schema: Type[ToolInput] = XLSToolInput
    return_direct: bool = False

    def run(self, input_params: Dict = None, *args, **kwarg) -> ToolOutput:
        try:
            path = get_file_path(input_params)
            mode = input_params.get("only_headers", False)
            return process_file(path, "headers" if mode else "all")

        except Exception as e:
            return ToolOutputError(error=str(e))


def get_file_path(input_params):
    path = input_params.get("path")
    if not path:
        raise ToolException("Path is required")
    copilot_debug(f"Tool XLSTool input: {path}")
    copilot_debug(f"Current directory: {os.getcwd()}")
    if not Path(path).exists() or not Path(path).is_file():
        raise ToolException(f"Filename {path} doesn't exist")

    return path
