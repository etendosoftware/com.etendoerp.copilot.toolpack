import pytest
from langsmith import unit
from tools import TemplateTool

@unit
def test_template_tool_with_json_input():
    tool = TemplateTool()
    input_data = {"input1": "value1", "input2": "value2"}
    
    result = tool.run(input=input_data)

    assert result["message"] == "Mail sent successfully"

@unit
def test_template_tool_with_string_input():
    tool = TemplateTool()
    input_data = '{"input1": "value1", "input2": "value2"}'

    result = tool.run(input=input_data)

    assert result["message"] == "Mail sent successfully"

@unit
def test_template_tool_with_missing_input():
    tool = TemplateTool()
    input_data = {"input1": "value1"}

    result = tool.run(input=input_data)

    assert result["message"] == "Mail sent successfully"

@unit
def test_template_tool_with_extra_parameters():
    tool = TemplateTool()
    input_data = {"input1": "value1", "input2": "value2", "extra_param": "extra_value"}

    result = tool.run(input=input_data)

    assert result["message"] == "Mail sent successfully"

@unit
def test_template_tool_with_invalid_json():
    tool = TemplateTool()
    input_data = "Invalid JSON string"

    with pytest.raises(Exception):
        tool.run(input=input_data)
