import os
from pathlib import Path
from langchain_core.pydantic_v1 import Field, BaseModel
from typing import List, Type
from copilot.core.tool_wrapper import ToolWrapper
from copilot.core.utils import copilot_debug

class PdfToImagesToolInput(BaseModel):
    path: str = Field(description="Path of the PDF to be converted")

class PdfToImagesTool(ToolWrapper):
    name = "PdfToImagesTool"
    description = "Converts a PDF file into an array of images, each representing a page of the PDF."
    args_schema: Type[BaseModel] = PdfToImagesToolInput

    @staticmethod
    def convert_to_pil_img(bitmap):
        import pypdfium2.internal as pdfium_i
        dest_mode = pdfium_i.BitmapTypeToStrReverse[bitmap.format]
        import PIL.Image
        image = PIL.Image.frombuffer(
            dest_mode,  # target color format
            (bitmap.width, bitmap.height),  # size
            bitmap.buffer,  # buffer
            "raw",  # decoder
            bitmap.mode,  # input color format
            bitmap.stride,  # bytes per line
            1,  # orientation (top->bottom)
        )
        image.readonly = False
        return image

    def run(self, input_params, *args, **kwargs):
        try:
            import pypdfium2 as pdfium

            pdf_path = input_params.get('path')

            if not Path(pdf_path).is_file():
                raise Exception(f"Filename {pdf_path} doesn't exist")

            pdf = pdfium.PdfDocument(pdf_path)
            n_pages = len(pdf)
            images = []

            for page_number in range(n_pages):
                page = pdf.get_page(page_number)
                bitmap = page.render(scale=2.0)
                pil_image = self.convert_to_pil_img(bitmap)
                # store the image to a temp path
                pil_image.save(f'/tmp/page_{page_number}.png')
                # append temp file path to the images list
                images.append(f'/tmp/page_{page_number}.png')

            return images
        except Exception as e:
            errmsg = f"An error occurred: {e}"
            copilot_debug(errmsg)
            raise Exception(errmsg)

        copilot_debug(f"Tool PdfToImagesTool output: {images}")
        return images
