import os
from typing import Type, Dict

from langsmith import traceable

from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper


class FileCopyToolInput(ToolInput):
    source_path: str = ToolField(
        title="Source Path",
        description='''The path of the file to read.'''
    )
    destination_directory: str = ToolField(
        title="Destination Directory",
        description='''The path of the directory to copy the file.'''
    )


class FileCopyTool(ToolWrapper):
    name = 'FileCopyTool'
    description = ('This tool receives two paths, one of a file and another of a directory, copies the file to the '
                   'directory. Returns the path of the copied file. Example of input: { "source_path": '
                   '"/home/user/file.txt", "destination_directory": "/home/user/destination_directory" }')
    args_schema: Type[ToolInput] = FileCopyToolInput

    @traceable
    def run(self, input_params: Dict, *args, **kwargs):
        import shutil

        source_path = input_params.get('source_path')
        destination_directory = input_params.get('destination_directory')

        # Ensure the destination directory exists
        os.makedirs(destination_directory, exist_ok=True)

        # Copy the file
        destination_path = shutil.copy(source_path, destination_directory)

        return {"file_path": destination_path}
