import os
from typing import Type, Dict

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

    # Listar y acumular los nombres de archivos y directorios
    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        result += full_path + "\n"

        # Si es un directorio y la recursividad está habilitada, acumular los resultados de forma recursiva
        if recursive and os.path.isdir(full_path):
            result += get_directory_contents(full_path, recursive)

    return {"message": result}


class PrintDirectoryTool(ToolWrapper):
    name: str = "PrintDirectoryTool"
    description: str = (
        """ This tool prints the files and directories of the a directory."""
    )
    args_schema: Type[ToolInput] = PrintDirToolInput

    @traceable
    def run(self, input_params: Dict, *args, **kwargs):
        p_recursive = input_params.get("recursive")
        p_path = input_params.get("path")

        return get_directory_contents(p_path, p_recursive)
