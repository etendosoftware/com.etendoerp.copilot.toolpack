import os
from typing import Type, Dict

from pydantic import Field, BaseModel

from copilot.core.tool_wrapper import ToolWrapper
from langchain_experimental.utilities import PythonREPL


class CodeRunToolInput(BaseModel):
    command: str = Field(
        title="Python Command",
        description='''A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`. 
        If execution fails, install needed libraries with `!pip install <library>`.'''
    )


class CodeRunTool(ToolWrapper):
    name = 'CodeRunTool'
    description = ('A Python shell tool. Example of input: { "command": "print(\'Hello, World!\')" }')
    args_schema: Type[BaseModel] = CodeRunToolInput

    def run(self, input_params: Dict, *args, **kwargs):
        command = input_params.get('command')

        try:
            # Execute the command using PythonREPL
            repl = PythonREPL()
            result = repl.run(command)
            return {"output": result}
        except Exception as e:
            return {"error": str(e)}
