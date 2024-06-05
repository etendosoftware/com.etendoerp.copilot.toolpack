import os
from typing import Dict, Type

from pydantic import Field, BaseModel

from copilot.core.tool_wrapper import ToolWrapper


class ReadFileToolInput(BaseModel):
    filepath: str = Field(
        title="Filepath",
        description='''The path of the file to read.''',
    )


class ReadFileTool(ToolWrapper):
    name = 'ReadFileTool'
    description = ('This is a tool for reading files. Receives "filepath" string parameter. The "filepath" parameter '
                   'is the path of the file to read. The tool will return the content of the file.'
                   'Example of input: { "filepath": "/tmp/test.txt" }')
    args_schema: Type[BaseModel] = ReadFileToolInput

    def run(self, input_params: Dict, *args, **kwargs):
        # if json is a string, convert it to json, else, use the json
        p_filepath = input_params.get('filepath')
        # read the file
        file_content = open(p_filepath).read()

        return {"message": file_content}
