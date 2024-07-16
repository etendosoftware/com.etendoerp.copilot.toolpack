import os

from langsmith import traceable
from copilot.core.tool_wrapper import ToolWrapper


class FileCopyTool(ToolWrapper):
    name = 'FileCopyTool'
    description = ('This tool receives two paths, one of a file and another of a directory, copies the file to the directory. Returns the path of the copied file. Example of input: { "source_path": "/home/user/file.txt", "destination_directory": "/home/user/destination_directory" }' )
    inputs = ['source_path', 'destination_directory']
    outputs = ['file_path']

    @traceable
    def run(self, input, *args, **kwargs):
        import shutil
        import json

        # if json is a string, convert it to json, else, use the json
        if isinstance(input, str):
            json = json.loads(input)
        else:
            json = input
        source_path = json.get('source_path')
        destination_directory = json.get('destination_directory')

        # Ensure the destination directory exists
        os.makedirs(destination_directory, exist_ok=True)

        # Copy the file
        destination_path = shutil.copy(source_path, destination_directory)

        return {"file_path": destination_path }
