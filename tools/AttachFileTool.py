import base64
import os
from typing import Type, Optional, Dict

from core.utils.etendo_utils import call_webhook, get_etendo_host, get_etendo_token
from copilot.core.tool_input import ToolInput, ToolField
from copilot.core.tool_wrapper import ToolWrapper
from baseutils.logging_envvar import copilot_debug


class AttachFileInput(ToolInput):
    filepath: str = ToolField(description="The path of the file to upload")
    ad_tab_id: str = ToolField(
        description="A string of 32 chars which is the ID of the Tab"
    )
    record_id: str = ToolField(
        description="A string of 32 chars which is the ID of the record"
    )


class AttachFileTool(ToolWrapper):
    """A tool to attach a file by uploading it to an API.

    Attributes:
        name (str): The name of the tool.
        description (str): A brief description of the tool.
    """

    name: str = "AttachFileTool"
    description: str = (
        "Uploads a file to an API after checking its existence and accessibility."
    )
    args_schema: Type[ToolInput] = AttachFileInput
    return_direct: bool = False

    def run(self, input_params: Dict, *args, **kwargs) -> Dict:
        filepath = input_params.get("filepath")
        ad_tab_id = input_params.get("ad_tab_id")
        record_id = input_params.get("record_id")

        full_file_path = "/app" + filepath
        copilot_debug(f"Tool AttachTool input: {full_file_path}")
        copilot_debug(f"Current directory: {os.getcwd()}")
        if not os.path.isfile(full_file_path) or not os.access(full_file_path, os.R_OK):
            full_file_path = ".." + filepath
        if not os.path.isfile(full_file_path) or not os.access(full_file_path, os.R_OK):
            full_file_path = filepath
        # Check if the file exists and is accessible
        if not os.path.isfile(full_file_path) or not os.access(full_file_path, os.R_OK):
            return {"error": "File does not exist or is not accessible"}

        # Read the file and encode it in base64
        with open(full_file_path, "rb") as file:
            file_content = file.read()
            file_base64 = base64.b64encode(file_content).decode("utf-8")
        file_name = os.path.basename(filepath)
        access_token = get_etendo_token()
        etendo_host = get_etendo_host()
        copilot_debug(f"ETENDO_HOST: {etendo_host}")
        return self.attach_file(
            etendo_host, access_token, ad_tab_id, record_id, file_name, file_base64
        )

    def attach_file(
        self, url, access_token, ad_tab_id, record_id, file_name, file_base64
    ):
        webhook_name = "AttachFile"
        body_params = {
            "ADTabId": ad_tab_id,
            "RecordId": record_id,
            "FileName": file_name,
            "FileContent": file_base64,
        }
        post_result = call_webhook(access_token, body_params, url, webhook_name)
        return post_result


def _get_headers(access_token: Optional[str]) -> Dict:
    """
    This method generates headers for an HTTP request.

    Parameters:
    access_token (str, optional): The access token to be included in the headers. If provided, an 'Authorization' ToolField
     is added to the headers with the value 'Bearer {access_token}'.

    Returns:
    dict: A dictionary representing the headers. If an access token is provided, the dictionary includes an
     'Authorization' field.
    """
    headers = {}

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers
