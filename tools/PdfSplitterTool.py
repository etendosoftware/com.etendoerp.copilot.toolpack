from pathlib import Path
from typing import Type

from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper
from copilot.core.utils import copilot_debug


class PdfSplitterToolInput(ToolInput):
    path: str = ToolField(description="Path of the PDF to be split")


class PdfSplitterTool(ToolWrapper):
    name: str = "PdfSplitterTool"
    description: str = "Splits a PDF file into separate single-page PDF files."
    args_schema: Type[ToolInput] = PdfSplitterToolInput

    def run(self, input_params, *args, **kwargs):
        try:
            from PyPDF2 import PdfReader, PdfWriter
            pdf_path = input_params.get("path")

            if not Path(pdf_path).is_file():
                raise Exception(f"Filename {pdf_path} doesn't exist")

            output_paths = []
            reader = PdfReader(pdf_path)
            n_pages = len(reader.pages)

            for page_number in range(n_pages):
                writer = PdfWriter()
                writer.add_page(reader.pages[page_number])

                output_path = f"/tmp/page_{page_number + 1}.pdf"
                with open(output_path, "wb") as output_file:
                    writer.write(output_file)

                output_paths.append(output_path)

            copilot_debug(f"PDF successfully split into {n_pages} files.")
            return output_paths

        except Exception as e:
            errmsg = f"An error occurred: {e}"
            copilot_debug(errmsg)
            raise Exception(errmsg)
