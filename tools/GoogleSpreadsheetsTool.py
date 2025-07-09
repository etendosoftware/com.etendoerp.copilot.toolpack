from typing import Dict, Optional, Type

from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import (
    ToolOutput,
    ToolOutputError,
    ToolOutputMessage,
    ToolWrapper,
)
from tools.GoogleServiceUtil import GoogleServiceUtil


class GoogleSpreadsheetToolInput(ToolInput):
    alias: str = ToolField(description="Alias of the OAuth token to use.")
    mode: str = ToolField(description="Action to perform")
    name: Optional[str] = ToolField(
        default=None,
        description="Name of spreadsheet to create (required for create/upload mode). "
        "",
    )
    file_id: Optional[str] = ToolField(
        default=None,
        description="ID of the spreadsheet to read (required for read mode).",
    )
    range: Optional[str] = ToolField(
        default=None, description="Cell range to read (optional, defaults to A1:Z1000)."
    )
    file_path: Optional[str] = ToolField(
        default=None,
        description="Local path to the CSV file to upload (required for upload mode).",
    )


def download_mode(alias, input_params):
    file_id = input_params.get("file_id")
    if not file_id:
        return ToolOutputError(error="Missing 'file_id' parameter for download mode.")
    range_ = input_params.get("range", "A1:Z1000")
    try:
        # Download the sheet as CSV and save it to a temporary path
        file_path = GoogleServiceUtil.download_sheet_as_csv(alias, file_id, range_)
        return ToolOutputMessage(message=f"✅ CSV file downloaded at: {file_path}")
    except Exception as e:
        return ToolOutputError(error=f"❌ Failed to download sheet as CSV: {str(e)}")


def list_mode(alias):
    files = GoogleServiceUtil.list_accessible_files("spreadsheet", alias)
    if not files:
        return ToolOutputMessage(message="No spreadsheets found.")
    formatted = "\n".join([f"- {f['name']} (ID: {f['id']})" for f in files])
    return ToolOutputMessage(message=f"Spreadsheets found:\n{formatted}")


def create_mode(alias, input_params):
    name = input_params.get("name")
    if not name:
        return ToolOutputError(error="Missing 'name' parameter for create mode.")
    created = GoogleServiceUtil.create_drive_file(
        name, "application/vnd.google-apps.spreadsheet", alias
    )
    url = f"https://docs.google.com/spreadsheets/d/{created['id']}/edit"
    return ToolOutputMessage(
        message=f"Spreadsheet '{created['name']}' created with ID: {created['id']}. Can be accessed at: {url}"
    )


def read_mode(alias, input_params):
    file_id = input_params.get("file_id")
    if not file_id:
        return ToolOutputError(error="Missing 'file_id' parameter for read mode.")
    range_ = input_params.get("range", "A1:Z1000")
    values = GoogleServiceUtil.read_sheet(alias, file_id, range_)
    if not values:
        return ToolOutputMessage(message="Sheet is empty.")
    formatted_rows = "\n".join([", ".join(map(str, row)) for row in values])
    return ToolOutputMessage(message=f"Spreadsheet content:\n{formatted_rows}")


def upload_mode(alias, input_params):
    file_path = input_params.get("file_path")
    name = input_params.get("name") or file_path.split("/")[-1]
    if not file_path:
        return ToolOutputError(error="Missing 'file_path' parameter for upload mode.")
    try:
        uploaded = GoogleServiceUtil.upload_csv_as_spreadsheet(alias, file_path, name)
        link = f"https://docs.google.com/spreadsheets/d/{uploaded['id']}/edit"
        return ToolOutputMessage(
            message=f"✅ CSV file '{uploaded['name']}' uploaded successfully.\n🔗 Link: {link}"
        )
    except Exception as e:
        return ToolOutputError(error=f"❌ Failed to upload CSV: {str(e)}")


class GoogleSpreadsheetsTool(ToolWrapper):
    name: str = "GoogleSpreadsheetsTool"
    description: str = (
        "Tool to interact with Google Spreadsheets through Google Drive API. "
        "The tool have the following modes: "
        "- list: List all accessible spreadsheets.\n"
        "- create: Create a new spreadsheet with the specified name.\n"
        "- upload: Upload a csv file to Google Drive as a new spreadsheet.\n"
        "- read: Read the content of a specified spreadsheet.\n"
        "- download: Download a specified spreadsheet as a CSV file."
    )
    args_schema: Type[ToolInput] = GoogleSpreadsheetToolInput
    return_direct: bool = False

    def run(self, input_params: Dict = None, *args, **kwargs) -> ToolOutput:
        try:
            alias = input_params["alias"]
            mode = input_params["mode"].lower()

            if mode == "list":
                return list_mode(alias)

            elif mode == "create":
                return create_mode(alias, input_params)
            elif mode == "upload":
                return upload_mode(alias, input_params)
            elif mode == "read":
                return read_mode(alias, input_params)
            elif mode == "download":
                return download_mode(alias, input_params)

            else:
                return ToolOutputError(error=f"Unsupported mode: {mode}")

        except Exception as e:
            return ToolOutputError(error=f"GoogleSheetsTool error: {str(e)}")
