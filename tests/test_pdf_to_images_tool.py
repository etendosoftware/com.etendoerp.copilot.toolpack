from unittest.mock import patch, MagicMock

import pytest
from langsmith import unit
from langchain_core.pydantic_v1 import ValidationError

from tools import PdfToImagesTool
from tools.PdfToImagesTool import PdfToImagesToolInput


@unit
def test_file_does_not_exist():
    tool = PdfToImagesTool()
    invalid_pdf_path = "/path/to/nonexistent.pdf"

    input_params = {"path": invalid_pdf_path}

    with pytest.raises(Exception, match=r".*doesn't exist.*"):
        tool.run(input_params)


@unit
def test_not_a_pdf_file(requests_mock):
    tool = PdfToImagesTool()
    not_a_pdf_path = "/path/to/not_a_pdf.txt"

    # Mock for Path().is_file()
    with patch("pathlib.Path.is_file", return_value=True):
        patch('pypdfium2.PdfDocument', side_effect=ValueError("Invalid PDF")).start()

        input_params = {"path": not_a_pdf_path}

        with pytest.raises(Exception, match=r".*Invalid PDF.*"):
            tool.run(input_params)


@unit
def test_pdf_with_no_pages(requests_mock):
    tool = PdfToImagesTool()
    empty_pdf_path = "/path/to/empty.pdf"

    mock_pdf = MagicMock()

    # Mock for Path().is_file()
    with patch("pathlib.Path.is_file", return_value=True):
        patch('pypdfium2.PdfDocument', return_value=mock_pdf).start()
        mock_pdf.__len__.return_value = 0

        input_params = {"path": empty_pdf_path}
        result = tool.run(input_params)

        assert result == []


@unit
def test_invalid_input_params():
    with pytest.raises(ValidationError):
        PdfToImagesToolInput(fieldx=123)
