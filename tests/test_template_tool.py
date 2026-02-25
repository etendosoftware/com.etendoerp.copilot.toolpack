import pytest

from tools import TemplateTool

TWO_INPUT_RESPONSE = "Input1: value1, Input2: value2"


def test_template_tool_with_json_input():
    tool = TemplateTool()
    input_data = {"input1": "value1", "input2": "value2"}

    result = tool.run(input=input_data)

    expected_message = TWO_INPUT_RESPONSE
    assert result["message"] == expected_message


def test_template_tool_with_string_input():
    tool = TemplateTool()
    input_data = '{"input1": "value1", "input2": "value2"}'

    result = tool.run(input=input_data)

    expected_message = TWO_INPUT_RESPONSE
    assert result["message"] == expected_message


def test_template_tool_with_missing_input():
    tool = TemplateTool()
    input_data = {"input1": "value1"}

    result = tool.run(input=input_data)

    expected_message = "Input1: value1, Input2: None"
    assert result["message"] == expected_message


def test_template_tool_with_extra_parameters():
    tool = TemplateTool()
    input_data = {"input1": "value1", "input2": "value2", "extra_param": "extra_value"}

    result = tool.run(input=input_data)

    expected_message = TWO_INPUT_RESPONSE
    assert result["message"] == expected_message


def test_template_tool_with_invalid_json():
    tool = TemplateTool()
    input_data = "Invalid JSON string"

    with pytest.raises(Exception):
        tool.run(input=input_data)
