import os
from typing import Type, Dict
from pydantic import Field, BaseModel
from copilot.core.tool_wrapper import ToolWrapper

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
        from langchain_experimental.utilities import PythonREPL
        command = input_params.get('command')

        if not command:
            return {"error": "No command provided"}

        # Execute the command using PythonREPL
        repl = PythonREPL()
        result = repl.run(command)
        if result is None:
            return {"error": "No output"}
        # if result starts with SyntaxError, ZeroDivisionError, or Exception, return error
        if result.startswith("SyntaxError") or result.startswith("ZeroDivisionError") or result.startswith("Exception"):
            return {"error": result}
        return {"output": result}
