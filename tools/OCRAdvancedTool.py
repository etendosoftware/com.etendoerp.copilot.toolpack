import base64
import os
from pathlib import Path
from typing import Final, Type

from langchain.chat_models import init_chat_model
from pydantic import BaseModel

from copilot.baseutils.logging_envvar import (
    copilot_debug,
    read_optional_env_var,
)
from copilot.core.threadcontextutils import read_accum_usage_data
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper
from copilot.core.utils.models import get_proxy_url

# Import schema loader
from tools.schemas import list_available_schemas, load_schema

GET_JSON_PROMPT: Final[
    str
] = """ Thoroughly analyze and extract all the information from the image(s).
 DO NOT SUMMARIZE OR OMIT INFORMATION, EVEN IF IT IS REPEATED OR THERE ARE SIMILAR PARTS.
 The information has to be returned in JSON format.
"""

GET_JSON_WITH_REFERENCE_PROMPT: Final[
    str
] = """You are an expert in extracting information from invoices and structured documents. Extract the key information from the document provided in the images.

Strict instructions:
- Use ONLY the reference image (first image) to determine what data to extract. The data must be clearly highlighted in red with boxes in the reference image. GIVE ABSOLUTE PRIORITY to data indicated in red; ignore or do not consider data labeled in black or other colors if they do not match the red highlights.
- If a data point is not indicated or highlighted in red in the reference image, DO NOT extract it or include it in the output. Leave it as null or empty.
- Use the exact text from the document for extractions, but only from the areas highlighted in red.
- The information has to be returned in JSON format.
- DO NOT SUMMARIZE OR OMIT INFORMATION from the highlighted red areas, EVEN IF IT IS REPEATED OR THERE ARE SIMILAR PARTS.

The first image is the REFERENCE with red markers. The following images are the document to extract data from.
"""

SUPPORTED_MIME_FORMATS = {
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "PDF": "application/pdf",
}


class OCRAdvancedToolInput(ToolInput):
    path: str = ToolField(
        description="Absolute or relative path to the image or PDF file to be processed. "
        "The file must exist in the local file system."
    )
    question: str = ToolField(
        description="Specific instructions or question describing what information to extract from the document. "
        "Be precise about the data fields needed (e.g., 'Extract invoice number, date, total amount, and vendor name'). "
        "Clear instructions improve extraction accuracy."
    )
    structured_output: str = ToolField(
        default=None,
        description="Optional. Specify a schema name to use structured output format (e.g., 'Invoice'). "
        "Available schemas are loaded from tools/schemas/ directory. "
        "When specified, the response will follow the predefined schema structure. "
        "Leave empty or None for unstructured JSON extraction.",
    )
    disable_threshold_filter: bool = ToolField(
        default=False,
        description=(
            "Optional. When True, ignore the configured similarity threshold and return the most similar "
            "reference found in the agent database (disables threshold filtering). Default: False."
        ),
    )


def convert_to_pil_img(bitmap):
    """Converts a pypdfium2 bitmap to a PIL Image.

    Args:
        bitmap: The pypdfium2 bitmap object to convert.

    Returns:
        PIL.Image: The converted PIL Image object.
    """
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


def get_image_payload_item(img_b64, mime):
    """Creates an image payload item for the vision model.

    Args:
        img_b64 (str): Base64 encoded image data.
        mime (str): MIME type of the image.

    Returns:
        dict: A dictionary representing the image payload item.
    """
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{img_b64}", "detail": "high"},
    }


def checktype(ocr_image_url, mime):
    """Checks if the MIME type is supported for OCR processing.

    Args:
        ocr_image_url (str): The path to the image file.
        mime (str): The MIME type of the file.

    Raises:
        ValueError: If the MIME type is not supported.
    """
    if mime not in SUPPORTED_MIME_FORMATS.values():
        raise ValueError(
            f"File {ocr_image_url} invalid file format with mime {mime}. Supported formats: {SUPPORTED_MIME_FORMATS}."
        )


def read_mime(ocr_image_url):
    """Reads the MIME type of a file.

    Args:
        ocr_image_url (str): The path to the file.

    Returns:
        str or None: The MIME type of the file, or None if unable to determine.
    """
    import filetype

    try:
        guess_result = filetype.guess(ocr_image_url)
        mime = guess_result.mime if guess_result else None
    except Exception as e:
        copilot_debug(f"Error reading mime type: {e}")
        mime = None
    return mime


def get_file_path(input_params):
    """Resolves the file path from input parameters.

    Args:
        input_params (dict): The input parameters containing the path.

    Returns:
        str: The resolved absolute file path.
    """
    rel_path = input_params.get("path")
    ocr_image_url = "/app" + rel_path
    copilot_debug(f"Tool OCRAdvancedTool input: {ocr_image_url}")
    copilot_debug(f"Current directory: {os.getcwd()}")
    if not Path(ocr_image_url).exists():
        ocr_image_url = ".." + rel_path
    if not Path(ocr_image_url).exists():
        ocr_image_url = rel_path
    if not Path(ocr_image_url).is_file():
        raise FileNotFoundError(f"Filename {ocr_image_url} doesn't exist")
    return ocr_image_url


def image_to_base64(image_path):
    """Converts an image file to base64 encoded string.

    Args:
        image_path (str): The path to the image file.

    Returns:
        str: The base64 encoded string of the image.
    """
    with open(image_path, "rb") as image_file:
        image_binary_data = image_file.read()
        base64_encoded = base64.b64encode(image_binary_data).decode("utf-8")
        return base64_encoded


def recopile_files(
    base64_images, filenames_to_delete, folder_of_appended_file, mime, ocr_image_url
):
    """Processes files and converts them to base64 images, handling PDFs and other formats.

    Args:
        base64_images (list): List to append base64 encoded images to.
        filenames_to_delete (list): List to append temporary filenames to for cleanup.
        folder_of_appended_file (str): Folder path for temporary files.
        mime (str): MIME type of the file.
        ocr_image_url (str): Path to the original file.
    """
    import pypdfium2 as pdfium

    if mime == SUPPORTED_MIME_FORMATS["PDF"]:
        pdf = pdfium.PdfDocument(ocr_image_url)
        n_pages = len(pdf)
        uuid = os.urandom(16).hex()
        for page_number in range(n_pages):
            page = pdf.get_page(page_number)
            bitmap = page.render()
            pil_image = convert_to_pil_img(bitmap)

            page_image_filename = (
                f"{folder_of_appended_file}/{uuid}image_{page_number + 1}.jpeg"
            )
            # delete the file if it exists
            filenames_to_delete.append(page_image_filename)
            # Set secure file permissions (owner read/write only)
            old_umask = os.umask(0o077)
            try:
                pil_image.save(page_image_filename)
                os.chmod(page_image_filename, 0o600)
            finally:
                os.umask(old_umask)
            base64_images.append(image_to_base64(page_image_filename))
    elif mime not in [SUPPORTED_MIME_FORMATS["JPEG"], SUPPORTED_MIME_FORMATS["JPG"]]:
        # Convert to jpeg and get the base64
        from PIL import Image

        img = Image.open(ocr_image_url)
        img = img.convert("RGB")
        converted_image_filename = (
            f"{folder_of_appended_file}/{os.urandom(16).hex()}converted_img.jpeg"
        )
        # Set secure file permissions (owner read/write only)
        old_umask = os.umask(0o077)
        try:
            img.save(converted_image_filename)
            os.chmod(converted_image_filename, 0o600)
        finally:
            os.umask(old_umask)
        base64_images.append(image_to_base64(converted_image_filename))
        filenames_to_delete.append(converted_image_filename)
    else:
        base64_images.append(image_to_base64(ocr_image_url))


def prepare_images_for_ocr(ocr_image_url, mime):
    """Prepares images for OCR by converting them to base64 and handling PDFs.

    Args:
        ocr_image_url (str): Path to the image or PDF file.
        mime (str): MIME type of the file.

    Returns:
        tuple: A tuple containing (base64_images list, filenames_to_delete list).
    """
    filenames_to_delete = []
    base64_images = []
    folder_of_appended_file = os.path.dirname(ocr_image_url)

    recopile_files(
        base64_images,
        filenames_to_delete,
        folder_of_appended_file,
        mime,
        ocr_image_url,
    )

    return base64_images, filenames_to_delete


def cleanup_temp_files(filenames_to_delete):
    """Removes temporary files created during image processing.

    Args:
        filenames_to_delete (list): List of file paths to delete.
    """
    for filename_del in filenames_to_delete:
        try:
            os.remove(filename_del)
        except Exception as e:
            copilot_debug(f"Error deleting file {filename_del}: {e}")


def build_messages(base64_images, question, reference_image_base64=None):
    """Builds the message payload for the vision model.

    Sends images and reference as separate messages:
      - If a reference image is provided (as base64), sends a message with the reference
        image payload followed by a separate text message explaining that this
        is a reference example with markings.
      - Sends each real image as its own message (role 'user', content=[image payload]).
      - Finally sends the question as the last message.

    Args:
        base64_images: List of base64 encoded images from the document
        question: Question or prompt for extraction
        reference_image_base64: Optional base64 string of reference image from ChromaDB

    Returns:
        List of messages for the vision model
    """
    mime = SUPPORTED_MIME_FORMATS["JPEG"]
    messages = []
    # Add message for system prompt
    messages.append(
        {
            "role": "system",
            "content": (
                "You are an agent specializing in OCR. You may receive "
                "“reference images” with sectors marked in color (usually red) with "
                "labels to indicate relevant sectors."
                " Use them in real cases to prioritize content."
            ),
        }
    )

    # If reference image provided, add it as a separate message and a short
    # explanatory text message to tell the model this is the reference with
    # marked areas.
    if reference_image_base64:
        try:
            # Always use base64 from ChromaDB (never read from disk)
            reference_b64 = reference_image_base64
            copilot_debug("Using reference image from ChromaDB (base64)")

            ref_payload = get_image_payload_item(reference_b64, mime)
            # Wrap payload in a list for Langchain/Pydantic validation

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "I will send you an image as an example of a REFERENCE with "
                        "visual markers (red borders) indicating the positions/sections"
                        " where the most relevant data on the invoice is located."
                        " Next to the box is a label for the section. "
                        "Use it only as a template to know which areas are important "
                        "in real images."
                    ),
                }
            )
            messages.append({"role": "user", "content": [ref_payload]})
            messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "Understood. Now please send me the real images and specify "
                        "the information you need me to extract."
                    ),
                }
            )
            copilot_debug("Added reference image as a separate message")
        except Exception as e:
            copilot_debug(f"Error adding reference image as separate message: {e}")

    messages.append({"role": "user", "content": question})

    # Add each real image as a separate message
    for b64 in base64_images:
        try:
            img_payload = get_image_payload_item(b64, mime)
            # Wrap payload in a list for Langchain/Pydantic validation
            messages.append({"role": "user", "content": [img_payload]})
        except Exception as e:
            copilot_debug(f"Error adding image payload as separate message: {e}")

    # Finally add the textual question/prompt as the last message

    return messages


def get_vision_model_response(messages, model_name, structured_schema=None):
    """Invokes the vision model and returns the response.

    Args:
        messages: List of messages for the model
        model_name: Name of the vision model to use
        structured_schema: Optional Pydantic BaseModel class for structured output

    Returns:
        Response content (string for unstructured, dict for structured)
    """
    llm = init_chat_model(
        model=model_name,
        model_provider="openai" if model_name.startswith("gpt-") else None,
        temperature=1,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        base_url=get_proxy_url(),
        streaming=True,
        model_kwargs={"stream_options": {"include_usage": True}},
    )

    # Use structured output if schema is provided
    if structured_schema:
        llm_structured = llm.with_structured_output(structured_schema, include_raw=True)
        response_llm = llm_structured.invoke(messages)
        read_accum_usage_data(response_llm)
        # Convert Pydantic model to dict
        if isinstance(response_llm, BaseModel):
            return response_llm.model_dump()
        return response_llm

    # Default unstructured response
    response_llm = llm.invoke(messages)
    read_accum_usage_data(response_llm)
    return response_llm.content


class OCRAdvancedTool(ToolWrapper):
    """Advanced OCR tool with automatic reference template matching.

    Uses vision AI to extract structured data from images and PDFs. Automatically searches
    for similar reference templates with visual markers (red boxes) to guide the extraction.
    Returns data in JSON format.
    """

    name: str = "OCRAdvancedTool"
    description: str = (
        "Extracts structured data from images and PDF documents and returns JSON. "
        "Automatically finds and uses similar reference templates from the agent's vector database to guide extraction. "
        "Reference templates contain visual markers (red boxes) highlighting which data fields to extract. "
        "Best for: invoices, receipts, forms, contracts, and any structured document with consistent layouts. "
        "Reference images must be uploaded to the agent's database using the /addToVectorDB endpoint. "
        "Supports: JPEG, PNG, WebP, GIF, and multi-page PDF files. "
        "Supports extensible structured output schemas - add new schemas in tools/schemas/ directory. "
        "File must be accessible in the local file system."
    )

    args_schema: Type[ToolInput] = OCRAdvancedToolInput

    def run(self, input_params, *args, **kwargs):
        """Executes the OCR advanced tool to extract data from images or PDFs.

        Args:
            input_params (dict): The input parameters for the tool.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            dict or str: The extracted data in JSON format, or an error dictionary.
        """
        filenames_to_delete = []
        try:
            # Validate agent_id is available
            if not self.agent_id:
                error_msg = (
                    "OCRAdvancedTool requires agent_id to access the reference database. "
                    "Please ensure the tool is properly configured with an agent."
                )
                copilot_debug(error_msg)
                return {"error": error_msg}

            copilot_debug(f"OCRAdvancedTool called by agent: {self.agent_id}")

            # Get configuration and validate file
            openai_model = read_optional_env_var(
                "COPILOT_OCRADVANCEDTOOL_MODEL", "gpt-4.1"
            )
            ocr_image_url = get_file_path(input_params)
            mime = read_mime(ocr_image_url)
            checktype(ocr_image_url, mime)

            # Prepare images for OCR
            base64_images, filenames_to_delete = prepare_images_for_ocr(
                ocr_image_url, mime
            )

            # Search for similar reference using agent_id
            copilot_debug("Searching for similar reference image...")
            # Get the path to the first image for similarity search
            # For PDFs, use the temporary first page image; for images, use the original
            first_image_for_search = None

            if mime == SUPPORTED_MIME_FORMATS["PDF"] and filenames_to_delete:
                # Use first temporary page image
                first_image_for_search = filenames_to_delete[0]
            else:
                # Use the original image file
                first_image_for_search = ocr_image_url

            reference_image_path = None
            reference_image_base64 = None
            disable_threshold = input_params.get("disable_threshold_filter", False)
            if first_image_for_search and Path(first_image_for_search).exists():
                # Import from vectordb_utils instead of local function
                from copilot.core.vectordb_utils import find_similar_reference

                # When disable_threshold is True we request the most similar reference
                # ignoring any configured similarity threshold.
                reference_image_path, reference_image_base64 = find_similar_reference(
                    first_image_for_search,
                    self.agent_id,
                    ignore_env_threshold=disable_threshold,
                )

            # Determine which prompt to use
            if reference_image_path or reference_image_base64:
                default_prompt = GET_JSON_WITH_REFERENCE_PROMPT
                copilot_debug(
                    f"Using reference-based extraction with reference: {reference_image_path}"
                )
            else:
                default_prompt = GET_JSON_PROMPT
                copilot_debug("No reference found, using standard extraction")

            # Get question or use appropriate default prompt
            question = input_params.get("question", default_prompt)

            # Determine if structured output is requested
            structured_output_type = input_params.get("structured_output")
            structured_schema = None

            if structured_output_type:
                # Dynamically load the schema from ocr_schemas directory
                structured_schema = load_schema(structured_output_type)
                if structured_schema:
                    copilot_debug(
                        f"Using '{structured_output_type}' structured output schema"
                    )
                else:
                    available = list_available_schemas()
                    copilot_debug(
                        f"Schema '{structured_output_type}' not found. "
                        f"Available schemas: {available}"
                    )

            # Build messages and get response from vision model
            messages = build_messages(base64_images, question, reference_image_base64)
            response_content = get_vision_model_response(
                messages, openai_model, structured_schema
            )

            copilot_debug(f"Tool OCRAdvancedTool output: {response_content}")
            return response_content

        except Exception as e:
            # log stack trace of exception for debugging
            import traceback

            traceback_str = traceback.format_exc()
            copilot_debug(f"Stack trace: {traceback_str}")

            errmsg = f"An error occurred: {e}"
            copilot_debug(errmsg)
            return {"error": errmsg}
        finally:
            # Ensure temporary files are always cleaned up, even if an exception occurs
            cleanup_temp_files(filenames_to_delete)
