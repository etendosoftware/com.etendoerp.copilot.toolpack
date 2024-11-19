from typing import Type

from langsmith import traceable

from copilot.core.tool_input import ToolInput, ToolField
from copilot.core.tool_wrapper import ToolWrapper


class TemplateInput(ToolInput):
    input1: str = ToolField(description="The first input")
    input2: str = ToolField(description="The second input")


class TemplateTool(ToolWrapper):
    name: str = "TemplateTool"
    description: str = "This is a file template for creating new tools."

    args_schema: Type[ToolInput] = TemplateInput

    @traceable
    def run(self, input, *args, **kwargs):
        import json

        # if json is a string, convert it to js on, else, use the json
        if isinstance(input, str):
            json = json.loads(input)
        else:
            json = input
        p_input1 = json.get("input1")
        p_input2 = json.get("input2")
        # code here, for example:
        response = f"Input1: {p_input1}, Input2: {p_input2}"

        return {"message": response}
