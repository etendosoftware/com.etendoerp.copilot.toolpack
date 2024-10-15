from typing import Dict, Type


from copilot.core.tool_input import ToolInput, ToolField
from copilot.core.tool_wrapper import ToolWrapper


class CodbarToolInput(ToolInput):
    filepath: list[str] = ToolField(
        title="Filepath",
        description='''The paths of the images to read.''',
    )


class CodbarTool(ToolWrapper):
    name = 'CodbarTool'
    description = (
        'This tool reads a barcode from an image. Receives "filepath" as an array string parameter. The "filepath" '
        ' parameter are the paths of the image files to read. The tool will return an array of founded barcodes if '
        ' found. Example of input: { "filepath": ["/tmp/test.png", "/tmp/test1.png"] }')
    args_schema: Type[ToolInput] = CodbarToolInput

    def run(self, input_params: Dict, *args, **kwargs):
        p_filepath = input_params.get('filepath')

        barcodes = []
        for file in p_filepath:
            barcode_number = self.decode(file)
            if barcode_number:
                [barcodes.append(code) for code in barcode_number]
                print(f"Barcode Number: {barcode_number}")

        return {"message": barcodes}

    def decode(self, p_filepath):
        from pyzbar.pyzbar import decode
        from PIL import Image

        img = Image.open(p_filepath)
        try:
            decoded_list = decode(img)
            if len(decoded_list) == 0:
                return None
            print(type(decoded_list[0]))
            return [d.data.decode('utf-8') for d in decoded_list]
        except Exception as e:
            print(f"The CodbarTool failed to decode the image. Check requirements in Etendo documentation. Error: {e}")
            return None
