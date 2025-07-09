from typing import Dict, Optional, Type
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import (
    ToolOutput,
    ToolOutputError,
    ToolOutputMessage,
    ToolWrapper,
)


class GoogleDriveToolInput(ToolInput):
    alias: str = ToolField(description="Alias of the OAuth token to use.")
    mode: str = ToolField(description="Action to perform: 'list' or 'upload'.")

    # list
    file_type: Optional[str] = ToolField(
        default="spreadsheet",
        description="File type to filter (spreadsheet, doc, pdf, etc.). Used in 'list' mode.",
    )

    # upload
    file_path: Optional[str] = ToolField(
        default=None,
        description="Local path to the file to upload. Required for 'upload' mode.",
    )
    name: Optional[str] = ToolField(
        default=None,
        description="Name to assign to the uploaded file in Drive (optional).",
    )
    mime_type: Optional[str] = ToolField(
        default=None,
        description="MIME type of the file (e.g., 'application/pdf'). Optional.",
    )


class GoogleDriveTool(ToolWrapper):
    name: str = "GoogleDriveTool"
    description: str = (
        "Tool to interact with Google Drive. Supports:\n"
        "- 'list': list accessible files of a certain type.\n"
        "- 'upload': upload a local file to Drive."
    )
    args_schema: Type[ToolInput] = GoogleDriveToolInput
    return_direct: bool = False

    def run(self, input_params: Dict = None, *args, **kwargs) -> ToolOutput:
        from tools.GoogleServiceUtil import GoogleServiceUtil

        try:
            alias = input_params["alias"]
            mode = input_params["mode"].lower()

            if mode == "list":
                file_type = input_params.get("file_type")
                if not file_type:
                    return ToolOutputError(
                        error="Missing 'file_type' parameter for list mode."
                    )
                files = GoogleServiceUtil.list_accessible_files(file_type, alias)
                if not files:
                    return ToolOutputMessage(
                        message=f"No files of type '{file_type}' found."
                    )
                formatted = "\n".join([f"- {f['name']} (ID: {f['id']})" for f in files])
                return ToolOutputMessage(
                    message=f"📂 Files of type '{file_type}':\n{formatted}"
                )

            elif mode == "upload":
                alias = input_params["alias"]
                file_path = input_params["file_path"]
                drive_name = input_params.get("name") or file_path.split("/")[-1]
                mime_type = input_params.get("mime_type", "application/octet-stream")

                uploaded = GoogleServiceUtil.upload_file_simple(
                    alias, file_path, drive_name, mime_type
                )
                link = f"https://drive.google.com/file/d/{uploaded['id']}/view"
                return ToolOutputMessage(
                    message=f"✅ File '{uploaded['name']}' uploaded successfully.\n🔗 Link: {link}"
                )

            else:
                return ToolOutputError(
                    error=f"Unsupported mode: '{mode}'. Use 'list' or 'upload'."
                )

        except Exception as e:
            return ToolOutputError(error=f"❌ GoogleDriveTool error: {str(e)}")
