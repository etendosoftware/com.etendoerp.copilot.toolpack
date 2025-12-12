import base64
import json
import os
from pathlib import Path
from typing import Final, Optional, Type

from pydantic import BaseModel

from copilot.baseutils.logging_envvar import copilot_error
from copilot.baseutils.logging_envvar import (
    copilot_debug,
    read_optional_env_var,
)
from copilot.core.threadcontextutils import read_accum_usage_data
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper
from copilot.core.utils.agent import get_llm
from copilot.core.utils.etendo_utils import get_extra_info


# Import schema loader
from tools.schemas import list_available_schemas, load_schema

DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_PROVIDER = "openai"
# Default PDF rendering scale (3.0 = ~300 DPI, 4.0 = ~400 DPI)
# Higher values = better quality but larger file size and slower processing
DEFAULT_PDF_RENDER_SCALE = 2.0

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
OCR_TOOL_ID = "EB58EEA0AA804C219C4D64260550745A"  # OCR Tool ID in Etendo Classic


class OcrToolInput(ToolInput):
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
        description="Specify a schema name to use structured output format (e.g., 'Invoice'). "
        "Available schemas are loaded from tools/schemas/ directory. "
        "When specified, the response will follow the predefined schema structure. "
        "Leave None for unstructured JSON extraction.",
    )
    force_structured_output_compat: bool = ToolField(
        default=False,
        description=(
            "Optional. When True (or when the selected model starts with 'gpt-5'), do not use the LLM's "
            "structured-output wrapper. Instead the tool will request structured output by embedding the schema "
            "JSON directly into the system prompt for compatibility with older agents."
        ),
    )
    disable_threshold_filter: bool = ToolField(
        default=False,
        description=(
            "Optional. When True, ignore the configured similarity threshold and return the most similar "
            "reference found in the agent database (disables threshold filtering). Default: False."
        ),
    )
    scale: float = ToolField(
        default=DEFAULT_PDF_RENDER_SCALE,
        description=(
            "PDF render scale factor (e.g., 2.0 = ~200 DPI, 3.0 = ~300 DPI). "
            "Higher values yield better quality but larger size and slower processing. "
            f"Default: {DEFAULT_PDF_RENDER_SCALE}."
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


def get_image_payload_item(img_b64, mime, provider):
    """Creates an image payload item for the vision model.

    Args:
        img_b64 (str): Base64 encoded image data.
        mime (str): MIME type of the image.
        is_gemini (bool): Whether the target model is Gemini (uses different format).

    Returns:
        dict: A dictionary representing the image payload item.
    """
    if provider == "gemini":
        # Gemini format - no "detail" field
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
        }
    else:
        # OpenAI format - includes "detail" field
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
    copilot_debug(f"Tool OcrTool input: {ocr_image_url}")
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


def pil_image_to_base64(pil_image, format="JPEG", quality=85):
    """Converts a PIL Image directly to base64 without saving to disk.

    This is much faster than saving to disk and reading back.

    Args:
        pil_image: PIL Image object
        format: Image format (JPEG, PNG, etc.)
        quality: JPEG quality (1-100)

    Returns:
        str: Base64 encoded string of the image
    """
    import io

    buffer = io.BytesIO()
    pil_image.save(buffer, format=format, quality=quality, optimize=True)
    buffer.seek(0)
    base64_encoded = base64.b64encode(buffer.read()).decode("utf-8")
    buffer.close()
    return base64_encoded


def recopile_files(
    base64_images,
    filenames_to_delete,
    folder_of_appended_file,
    mime,
    ocr_image_url,
    scale,
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

        # Get PDF render scale from environment or use default
        render_scale = scale
        copilot_debug(
            f"Rendering PDF at scale {render_scale}x (~{render_scale * 96:.0f} DPI)"
        )

        for page_number in range(n_pages):
            page = pdf.get_page(page_number)
            # Render at configured resolution
            bitmap = page.render(scale=render_scale)
            pil_image = convert_to_pil_img(bitmap)

            # OPTIMIZATION: Convert directly to base64 in memory without disk I/O
            # This is much faster than saving to disk and reading back
            base64_str = pil_image_to_base64(pil_image, format="JPEG", quality=85)
            base64_images.append(base64_str)

    elif mime not in [SUPPORTED_MIME_FORMATS["JPEG"], SUPPORTED_MIME_FORMATS["JPG"]]:
        # Convert to jpeg and get the base64
        from PIL import Image

        img = Image.open(ocr_image_url)
        img = img.convert("RGB")

        # OPTIMIZATION: Convert directly to base64 in memory without disk I/O
        base64_str = pil_image_to_base64(img, format="JPEG", quality=85)
        base64_images.append(base64_str)
    else:
        base64_images.append(image_to_base64(ocr_image_url))


def prepare_images_for_ocr(ocr_image_url, mime, scale):
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
        scale,
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


def build_messages(
    base64_images,
    question,
    reference_image_base64=None,
    extra_system_content: Optional[str] = None,
    provider: str = "openai",
):
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
        is_gemini: Whether the target model is Gemini (affects payload format)

    Returns:
        List of messages for the vision model
    """
    mime = SUPPORTED_MIME_FORMATS["JPEG"]
    messages = []
    # Add message for system prompt
    sys_content = (
        "You are an agent specializing in OCR. You may receive "
        "\u201creference images\u201d with sectors marked in color (usually red) with "
        "labels to indicate relevant sectors."
        " Use them in real cases to prioritize content."
    )
    if extra_system_content:
        # Append extra system instructions (compatibility markers, etc.)
        sys_content = sys_content + "\n" + extra_system_content

    messages.append(
        {
            "role": "system",
            "content": sys_content,
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

            ref_payload = get_image_payload_item(reference_b64, mime, provider)
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
            img_payload = get_image_payload_item(b64, mime, provider)
            # Wrap payload in a list for Langchain/Pydantic validation
            messages.append({"role": "user", "content": [img_payload]})
        except Exception as e:
            copilot_debug(f"Error adding image payload as separate message: {e}")

    # Finally add the textual question/prompt as the last message

    return messages


def get_vision_model_response(
    messages, model_name, structured_schema=None, force_compat: bool = False
):
    """Invokes the vision model and returns the response.

    Args:
        messages: List of messages for the model
        model_name: Name of the vision model to use
        structured_schema: Optional Pydantic BaseModel class for structured output

    Returns:
        Response content (string for unstructured, dict for structured)
    """
    # Determine provider based on model name prefix
    if model_name.startswith("gpt-"):
        provider = "openai"
    elif model_name.startswith("gemini"):
        provider = "gemini"
    else:
        provider = None

    # GPT-5 models only support temperature=1
    if model_name.startswith("gpt-5"):
        temperature = 1
    else:
        temperature = 0

    copilot_debug(
        f"Using model: {model_name}, provider: {provider}, temperature: {temperature}"
    )

    llm = get_llm(provider=provider, model=model_name, temperature=temperature)

    # If caller explicitly requests compatibility-mode, skip the structured
    # wrapper and perform an unstructured invocation. The caller is expected
    # to have added the compatibility marker into the system prompt when
    # calling in this mode.
    if structured_schema and not force_compat:
        try:
            llm_structured = llm.with_structured_output(
                structured_schema, include_raw=True
            )
            response_llm = llm_structured.invoke(messages)
            read_accum_usage_data(response_llm)
            # Convert Pydantic model to dict
            if isinstance(response_llm, BaseModel):
                return response_llm.model_dump()
            return response_llm
        except Exception:
            # If structured wrapper fails for any reason, fall back to unstructured
            # invocation and return raw content.
            copilot_debug(
                "Structured wrapper failed, falling back to unstructured invocation"
            )

    # Default unstructured response
    response_llm = llm.invoke(messages)
    read_accum_usage_data(response_llm)
    # If the response object has 'content', return it; otherwise return as-is
    return getattr(response_llm, "content", response_llm)


def get_llm_model(agent_id: str):
    # if COPILOT_OCRTOOL_MODEL is set override the default model
    env_ocr_model = read_optional_env_var("COPILOT_OCRTOOL_MODEL", None)
    if env_ocr_model:
        provider = "gemini" if env_ocr_model.startswith("gemini") else "openai"
        return env_ocr_model, provider
    # Get model from ThreadContext extra_info if available
    model_name = None
    provider = None
    try:
        extra_info = get_extra_info()
        if extra_info:
            tools_config = extra_info.get("tool_config").get(agent_id).get(OCR_TOOL_ID)
            if tools_config:
                model_name = tools_config.get("model")
                provider = tools_config.get("provider")
    except Exception as e:
        copilot_error(f"Error reading ThreadContext extra_info: {e}")

    if model_name is None:
        model_name = DEFAULT_MODEL
        provider = DEFAULT_PROVIDER

    return model_name, provider


class OcrTool(ToolWrapper):
    """Advanced OCR tool with automatic reference template matching.

    Uses vision AI to extract structured data from images and PDFs. Automatically searches
    for similar reference templates with visual markers (red boxes) to guide the extraction.
    Returns data in JSON format.
    """

    name: str = "OcrTool"
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

    args_schema: Type[ToolInput] = OcrToolInput

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
                    "OcrTool requires agent_id to access the reference database. "
                    "Please ensure the tool is properly configured with an agent."
                )
                copilot_debug(error_msg)
                return {"error": error_msg}

            copilot_debug(f"OcrTool called by agent: {self.agent_id}")

            # Get configuration from extra_info or default
            openai_model, provider = get_llm_model(self.agent_id)

            copilot_debug(f"OcrTool using model from config: {openai_model}")
            model_requires_compat = openai_model.startswith("gpt-5")
            ocr_image_url = get_file_path(input_params)
            mime = read_mime(ocr_image_url)
            checktype(ocr_image_url, mime)
            scale = input_params.get("scale", DEFAULT_PDF_RENDER_SCALE)
            # Prepare images for OCR
            base64_images, filenames_to_delete = prepare_images_for_ocr(
                ocr_image_url, mime, scale
            )

            # Search for similar reference using agent_id
            copilot_debug("Searching for similar reference image...")
            reference_image_path = None
            reference_image_base64 = None

            # Get the path to the first image for similarity search
            # For PDFs and converted images, we need to save a temp file for the search
            first_image_for_search = None

            if mime == SUPPORTED_MIME_FORMATS["PDF"] and base64_images:
                # For PDFs converted in memory, we need a temp file for similarity search
                # Create just one temp file for the first page
                import io
                from PIL import Image

                uuid = os.urandom(16).hex()
                temp_search_file = (
                    f"{os.path.dirname(ocr_image_url)}/{uuid}_search.jpeg"
                )

                # Decode base64 back to image just for search
                img_data = base64.b64decode(base64_images[0])
                img = Image.open(io.BytesIO(img_data))
                img.save(temp_search_file, "JPEG", quality=85, optimize=True)
                first_image_for_search = temp_search_file
                filenames_to_delete.append(temp_search_file)
            else:
                # Use the original image file
                first_image_for_search = ocr_image_url

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
            default_prompt = self.get_prompt(
                reference_image_base64, reference_image_path
            )

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
            # Determine if compatibility mode is requested
            force_compat = input_params.get("force_structured_output_compat", False)
            if model_requires_compat and not force_compat:
                copilot_debug(
                    f"Model '{openai_model}' requires structured-output compatibility mode; enabling automatically"
                )
            force_compat = force_compat or model_requires_compat
            extra_system = None
            extra_system = self.read_structured_output(
                extra_system, force_compat, structured_schema
            )

            messages = build_messages(
                base64_images, question, reference_image_base64, extra_system, provider
            )
            response_content = get_vision_model_response(
                messages, openai_model, structured_schema, force_compat
            )

            copilot_debug(f"Tool OcrTool output: {response_content}")
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

    def read_structured_output(self, extra_system, force_compat, structured_schema):
        """Prepare structured-output compatibility instructions for the system prompt.

        When compatibility mode is enabled (either explicitly requested or required by the
        selected model) and a Pydantic structured schema is provided, this method will
        produce a JSON representation of the schema and return it as a string suitable
        for inclusion in the system prompt. This helps older agents (or models that do
        not support the structured-output wrapper) to understand the expected output
        format.

        Args:
            extra_system (str or None): Existing extra system prompt content. If a
                schema JSON is generated it will replace or extend this value.
            force_compat (bool): Whether to force compatibility/legacy mode.
            structured_schema (Optional[Type[BaseModel]]): Pydantic model class used to
                generate the expected output schema.

        Returns:
            str or None: The updated extra system prompt containing the schema JSON when
            compatibility mode is active and a schema is available, otherwise returns
            the unchanged `extra_system` value.
        """
        if force_compat and structured_schema:
            # Build a JSON representation of the structured schema and pass
            # it in the system prompt so older agents receive the expected
            # structured-output example.
            try:
                if hasattr(structured_schema, "model_json_schema"):
                    schema_json = structured_schema.model_json_schema()
                elif hasattr(structured_schema, "schema"):
                    schema_json = structured_schema.schema()
                else:
                    schema_json = {}
            except Exception as e:
                copilot_debug(f"Error generating schema JSON: {e}")
                schema_json = {}

            extra_system = (
                "Expected output JSON schema for structured output: "
                + json.dumps(schema_json, ensure_ascii=False, indent=2)
            )
            copilot_debug(
                "Structured output compatibility mode enabled: adding structured schema JSON to system prompt"
            )
        return extra_system

    def get_prompt(self, reference_image_base64, reference_image_path):
        """Return the default extraction prompt depending on reference availability.

        If a reference image (either as a base64 string or a filesystem path) is
        available, prefer the reference-based prompt that instructs the model to use
        the reference image as template guidance. Otherwise return the generic
        extraction prompt.

        Args:
            reference_image_base64 (Optional[str]): Base64-encoded reference image (if any).
            reference_image_path (Optional[str]): Filesystem path to a matched reference image.

        Returns:
            str: The selected prompt string to use as the default question for OCR.
        """
        if reference_image_path or reference_image_base64:
            default_prompt = GET_JSON_WITH_REFERENCE_PROMPT
            copilot_debug(
                f"Using reference-based extraction with reference: {reference_image_path}"
            )
        else:
            default_prompt = GET_JSON_PROMPT
            copilot_debug("No reference found, using standard extraction")
        return default_prompt
