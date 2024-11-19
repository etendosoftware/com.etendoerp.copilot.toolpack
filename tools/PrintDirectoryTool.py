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
    extensions: str = ToolField(
        default=None,
        description="If provided, the tool will only print files with the specified extensions. It should be a "
        "comma-separated list of extensions.",
    )
    ignore_folder: str = ToolField(
        default=None,
        description="If provided, the tool will ignore the specified folder.",
    )


@traceable
def get_directory_contents(path, recursive=False, extensions=None, ignore_folder=None):
    if extensions is not None and extensions != "" and isinstance(extensions, str):
        extensions = extensions.split(",")
        extensions = [ext.strip().lower() for ext in extensions]
    if not os.path.exists(path):
        return {"error": f"Path does not exist: {path}"}
    result = ""
    if recursive:
        for root, dirs, files in os.walk(path):
            # Filtra las carpetas ocultas eliminándolas de la lista `dirs`, también se eliminan las carpetas que se
            # encuentren en la lista `ignore_folder`
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and not (ignore_folder and d in ignore_folder)
            ]

            for file in files:
                # Ignora archivos ocultos
                if file.startswith(".") or (ignore_folder and file in ignore_folder):
                    continue
                if extensions:
                    if file.lower().endswith(tuple(extensions)):
                        result += os.path.abspath(os.path.join(root, file)) + "\n"
                else:
                    result += os.path.abspath(os.path.join(root, file)) + "\n"
    else:
        with os.scandir(path) as entries:
            for entry in entries:
                # Ignora tanto archivos como carpetas ocultas
                if entry.name.startswith(".") or (
                    ignore_folder and entry.name in ignore_folder
                ):
                    continue
                if entry.is_file():
                    if extensions:
                        if entry.name.lower().endswith(tuple(extensions)):
                            result += os.path.abspath(entry.path) + "\n"
                    else:
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
            p_extensions = input_params.get("extensions")
            p_ignore_folder = input_params.get("ignore_folder")
            if p_extensions and p_extensions != "":
                p_extensions = p_extensions.split(",")
            else:
                p_extensions = []
            if p_ignore_folder and p_ignore_folder != "":
                p_ignore_folder = p_ignore_folder.split(",")
            else:
                p_ignore_folder = []

            return get_directory_contents(
                p_path, p_recursive, p_extensions, p_ignore_folder
            )
        except Exception as e:
            return {
                "error": f"An error occurred while trying to print the directory: {str(e)}"
            }
