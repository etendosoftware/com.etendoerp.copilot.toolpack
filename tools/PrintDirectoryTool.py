import os
from typing import Dict, Type

from langsmith import traceable

from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper


class PrintDirToolInput(ToolInput):
    path: str = ToolField(description="The path of the directory to print")
    recursive: bool = ToolField(
        default=False,
        description="If true, the tool will print the files and directories recursively.",
    )


@traceable
def get_directory_contents(path, recursive=False):
    if not os.path.exists(path):
        return {"error": f"Path does not exist: {path}"}
    # Inicializar una variable para almacenar los resultados
    result = ""
    if recursive:
        for root, _, files in os.walk(path):
            for file in files:
                result += os.path.abspath(os.path.join(root, file)) + "\n"
    else:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_file():
                    result += os.path.abspath(entry.path) + "\n"

    return {"message": result}


class PrintDirectoryTool(ToolWrapper):
    name: str = "PrintDirectoryTool"
    description: str = (
        """ This tool prints the files and directories of the a directory."""
    )
    args_schema: Type[ToolInput] = PrintDirToolInput

    @traceable
    def run(self, input_params: Dict, *args, **kwargs):
        try:
            p_recursive = input_params.get("recursive")
            p_path = input_params.get("path")

            return get_directory_contents(p_path, p_recursive)
        except Exception as e:
            return {
                "error": f"An error occurred while trying to print the directory: {str(e)}"
            }
