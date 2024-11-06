import os
from typing import Type, Dict

from copilot.core.tool_input import ToolInput, ToolField
from copilot.core.tool_wrapper import ToolWrapper, ToolOutput


class CodbarToolInput(ToolInput):
    filepath: list[str] = ToolField(
        title="Filepath",
        description="""The paths of the images to read.""",
    )


def decode(p_filepath):
    from pyzbar.pyzbar import decode
    from PIL import Image

    if not os.path.exists(p_filepath):
        print(f"File not found: {p_filepath}")
        return None

    img = Image.open(p_filepath)
    try:
        decoded_list = decode(img)
        if len(decoded_list) == 0:
            return None
        print(type(decoded_list[0]))
        return [d.data.decode("utf-8") for d in decoded_list]
    except Exception as e:
        print(
            f"The CodbarTool failed to decode the image. Check requirements in Etendo documentation. Error: {e}"
        )
        return None


class CodbarTool(ToolWrapper):
    name: str = "CodbarTool"
    description: str = (
        'This tool reads a barcode from an image. Receives "filepath" as an array string parameter. The "filepath" '
        " parameter are the paths of the image files to read. The tool will return an array of founded barcodes if "
        ' found. Example of input: { "filepath": ["/tmp/test.png", "/tmp/test1.png"] }'
    )
    args_schema: Type[ToolInput] = CodbarToolInput

    def run(self, input_params: Dict, *args, **kwarg) -> ToolOutput:
        p_filepath = input_params.get("filepath")

        if not isinstance(p_filepath, list):
            raise ValueError("Expected 'filepath' to be a list of strings.")

        barcodes = []
        for file in p_filepath:
            barcode_number = decode(file)
            if barcode_number:
                [barcodes.append(code) for code in barcode_number]
                print(f"Barcode Number: {barcode_number}")

        return {"message": barcodes}
