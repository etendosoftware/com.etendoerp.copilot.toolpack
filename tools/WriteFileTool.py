from langsmith import traceable
import os
from typing import Type, Dict

from pydantic import Field, BaseModel

from copilot.core.tool_wrapper import ToolWrapper


class WriteFileToolInput(BaseModel):
    filepath: str = Field(
        title="Filepath",
        description='''The path of the file to write.'''
    )
    content: str = Field(
        title="Content",
        description='''The content of the file to write.'''
    )
    override: bool = Field(
        default=True,
        description='''If true, the tool will override the file.'''
    )
    lineno: int = Field(
        default=-1,
        description='''The line number where to write the content.'''
    )


class WriteFileTool(ToolWrapper):
    name = 'WriteFileTool'
    description = (
        'This is a tool for writing files. Receives: "filepath": string, "content": string, "lineno": integer.'
        'The "filepath" parameter is the path of the file to write.'
        'The "content" parameter is the content of the file to write.'
        'The "override" parameter is a boolean that indicates if the tool needs to override the file or not. '
        'The "lineno" parameter is the line number where to write the content. If the line number is not specified, '
        'the content will be appended to the end of the file.'
        'The tool will return the content of the file. '
        'Example of input: { "filepath": "/tmp/test.txt", "content": "Hello world", "override": true, "lineno": 1 }')
    args_schema: Type[BaseModel] = WriteFileToolInput

    @traceable
    def run(self, input_params: Dict, *args, **kwargs):
        # if json is a string, convert it to json, else, use the json

        p_filepath = input_params.get('filepath')
        p_content = input_params.get('content')
        p_lineno = input_params.get('lineno', -1)
        backup = False
        # if the file doesn't exist, create it
        file_content = ''
        if not os.path.exists(p_filepath):
            open(p_filepath, 'w').close()
        else:  # if the files exists, read it, make a backup(adds .bak%timestamp%) and write the content
            file_content = open(p_filepath).read()
            # backup the file
            import time
            import shutil
            shutil.copyfile(p_filepath, p_filepath + '.bak' + str(time.time()))
            backup = True
            # write the content
        if not input_params.get('override', True):
            if p_lineno == -1:
                file_content += p_content
            else:
                lines = file_content.split('\n')
                lines.insert(p_lineno, p_content)
                file_content = '\n'.join(lines)
            open(p_filepath, 'w').write(file_content)
        else:
            #  delete the file
            os.remove(p_filepath)
            # write the content
            open(p_filepath, 'w').write(p_content)

        msg = "File %s written successfully, backup: %s" % (p_filepath, backup)
        return {"message": msg}
