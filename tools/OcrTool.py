import base64
import os
from pathlib import Path
from typing import Final, Type

from langsmith import traceable

from copilot.core import utils
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper
from copilot.core.utils import copilot_debug

GET_JSON_PROMPT: Final[str] = ''' Thoroughly analyze and extract all the information from the image(s).
 DO NOT SUMMARIZE OR OMIT INFORMATION, EVEN IF IT IS REPEATED OR THERE ARE SIMILAR PARTS.
 The information has to be returned in JSON format.
'''

SUPPORTED_MIME_FORMATS = {
    "JPEG": 'image/jpeg',
    "JPG": 'image/jpeg',
    "PNG": 'image/png',
    "WEBP": 'image/webp',
    "GIF": 'image/gif',
    "PDF": 'application/pdf'
}


class OcrToolInput(ToolInput):
    path: str = ToolField(description="path of the image to be processed")
    question: str = ToolField(
        description="Contextual question to be asked to the model, where is specified the information to be extracted "
                    "from the image. This is mandatory and very important to get precise results.")


@traceable
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


@traceable
def get_image_payload_item(img_b64, mime):
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime};base64,{img_b64}",
            "detail": "high"
        }
    }


@traceable
def checktype(ocr_image_url, mime):
    if mime not in SUPPORTED_MIME_FORMATS.values():
        raise ValueError(
            f"File {ocr_image_url} invalid file format with mime {mime}. Supported formats: {SUPPORTED_MIME_FORMATS}.")


@traceable
def read_mime(ocr_image_url):
    import filetype
    try:
        mime = filetype.guess(ocr_image_url).mime
    except Exception as e:
        print(e)
        mime = None
    return mime


@traceable
def get_file_path(input_params):
    rel_path = input_params.get('path')
    ocr_image_url = '/app' + rel_path
    copilot_debug(f"Tool OcrTool input: {ocr_image_url}")
    copilot_debug(f"Current directory: {os.getcwd()}")
    if not Path(ocr_image_url).exists():
        ocr_image_url = '..' + rel_path
    if not Path(ocr_image_url).exists():
        ocr_image_url = rel_path
    if not Path(ocr_image_url).is_file():
        raise FileNotFoundError(f"Filename {ocr_image_url} doesn't exist")
    return ocr_image_url


@traceable
def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        image_binary_data = image_file.read()
        base64_encoded = base64.b64encode(image_binary_data).decode('utf-8')
        return base64_encoded


@traceable
def recopile_files(base64_images, filenames_to_delete, folder_of_appended_file, mime, ocr_image_url):
    import pypdfium2 as pdfium

    if mime == SUPPORTED_MIME_FORMATS['PDF']:
        pdf = pdfium.PdfDocument(ocr_image_url)
        n_pages = len(pdf)
        uuid = os.urandom(16).hex()
        for page_number in range(n_pages):
            page = pdf.get_page(page_number)
            bitmap = page.render(scale=2)
            pil_image = convert_to_pil_img(bitmap)

            page_image_filename = f"{folder_of_appended_file}/{uuid}image_{page_number + 1}.jpeg"
            # delete the file if it exists
            filenames_to_delete.append(page_image_filename)
            pil_image.save(page_image_filename)
            base64_images.append(
                image_to_base64(page_image_filename))
    elif mime not in [SUPPORTED_MIME_FORMATS['JPEG'], SUPPORTED_MIME_FORMATS['JPG']]:
        # Convert to jpeg and get the base64
        from PIL import Image
        img = Image.open(ocr_image_url)
        img = img.convert('RGB')
        converted_image_filename = f"{folder_of_appended_file}/{os.urandom(16).hex()}converted_img.jpeg"
        img.save(converted_image_filename)
        base64_images.append(image_to_base64(converted_image_filename))
        filenames_to_delete.append(converted_image_filename)
    else:
        base64_images.append(image_to_base64(ocr_image_url))


class OcrTool(ToolWrapper):
    """OCR (Optical Character Recognition) implementation using Vision
    Given an image it will extract the text and return as JSON
    """
    name = "OcrTool"
    description = (
        "This is a OCR tool implementation that returns an appropriate JSON object for the data in a local file (image "
        "or pdf). "
        "Its important to note that the file should be in the local file system. "
        "Is the best way to extract the data/information from a image or pdf file.")

    args_schema: Type[ToolInput] = OcrToolInput

    @traceable
    def run(self, input_params, *args, **kwargs):
        try:
            openai_model = utils.read_optional_env_var("COPILOT_OCRTOOL_MODEL", "gpt-4o")
            ocr_image_url = get_file_path(input_params)
            mime = read_mime(ocr_image_url)
            checktype(ocr_image_url, mime)

            filenames_to_delete = []
            base64_images = []
            folder_of_appended_file = os.path.dirname(ocr_image_url)
            recopile_files(base64_images, filenames_to_delete, folder_of_appended_file, mime, ocr_image_url)
            mime = SUPPORTED_MIME_FORMATS['JPEG']

            for filename_del in filenames_to_delete:
                os.remove(filename_del)
            content = []
            if 'question' in input_params:
                msg = input_params['question']
            else:
                msg = GET_JSON_PROMPT
            for b64 in base64_images:
                content.append(get_image_payload_item(b64, mime))
            messages = [
                {
                    "role": "user",
                    "content": content
                },
                {
                    "role": "user",
                    "content": msg
                }
            ]

            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=openai_model,
                             temperature=0,
                             max_tokens=None,
                             timeout=None,
                             max_retries=2)
            response_llm = llm.invoke(messages)
        except Exception as e:
            errmsg = f"An error occurred: {e}"
            copilot_debug(errmsg)
            return {
                "error": errmsg
            }
        copilot_debug(f"Tool OcrTool output: {response_llm.content}")
        return response_llm.content
