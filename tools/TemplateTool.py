import os

from copilot.core.tool_wrapper import ToolWrapper


class TemplateTool(ToolWrapper):
    name = 'TemplateTool'
    description = ('This is a file template for creating new tools.' )
    inputs = ['input1', 'input2']
    outputs = ['message']

    def run(self, input, *args, **kwargs):
        import json

        # if json is a string, convert it to js on, else, use the json
        if isinstance(input, str):
            json = json.loads(input)
        else:
            json = input
        p_input1 = json.get('input1')
        p_input2 = json.get('input2')
        # code here

        return {"message": "Mail sent successfully" }
