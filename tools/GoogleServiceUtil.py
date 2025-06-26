import csv
import json
import os
import re
import tempfile
from datetime import datetime
from typing import List, Optional

import requests

from copilot.core.threadcontext import ThreadContext
from copilot.core.utils import copilot_debug_curl


def get_token_by_alias(alias: str) -> str:
    tokens = ThreadContext.get_data("oauth_tokens")
    if not tokens or alias not in tokens:
        raise ValueError(f"Token with alias '{alias}' not found.")
    return tokens[alias]["token"]


class GoogleServiceUtil:
    APPLICATION_NAME = "Google Sheets Python Integration"
    DEFAULT_RANGE = "A1:Z1000"

    MIME_TYPES = {
        "spreadsheet": "application/vnd.google-apps.spreadsheet",
        "doc": "application/vnd.google-apps.document",
        "slides": "application/vnd.google-apps.presentation",
        "pdf": "application/pdf",
        "pdfs": "application/pdf",
    }

    @staticmethod
    def get_googleapi_service(token_alias, service_name, version):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        access_token = get_token_by_alias(token_alias)
        creds = Credentials(token=access_token)
        return build(service_name, version, credentials=creds)

    @staticmethod
    def get_sheets_service(token_alias: str):
        return GoogleServiceUtil.get_googleapi_service(token_alias, "sheets", "v4")

    @staticmethod
    def get_drive_service(token_alias: str):
        return GoogleServiceUtil.get_googleapi_service(token_alias, "drive", "v3")

    @staticmethod
    def extract_sheet_id_from_url(url: str) -> str:
        match = re.search(
            r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)", url
        )
        if not match:
            raise ValueError("Invalid URL. Couldn't extract spreadsheet ID.")
        return match.group(1)

    @staticmethod
    def get_tab_name(index: int, sheet_id: str, token_alias: str) -> str:
        service = GoogleServiceUtil.get_sheets_service(token_alias)
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = spreadsheet.get("sheets", [])
        if not sheets:
            raise Exception("Spreadsheet doesn't contain tabs.")
        if index >= len(sheets):
            raise Exception("Wrong tab number.")
        return sheets[index]["properties"]["title"]

    @staticmethod
    def read_sheet(
        token_alias: str, file_id: str, range_: Optional[str] = None
    ) -> List[List[str]]:
        service = GoogleServiceUtil.get_sheets_service(token_alias)
        range_ = range_ or GoogleServiceUtil.DEFAULT_RANGE
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=file_id, range=range_)
            .execute()
        )
        return result.get("values", [])

    @staticmethod
    def update_spreadsheet_values(
        file_id: str, token_alias: str, range_: str, values: List[List[object]]
    ) -> dict:
        service = GoogleServiceUtil.get_sheets_service(token_alias)
        body = {"range": range_, "majorDimension": "ROWS", "values": values}
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=file_id, range=range_, valueInputOption="RAW", body=body
            )
            .execute()
        )
        return result

    @staticmethod
    def list_accessible_files(file_type: str, token_alias: str) -> List[dict]:
        access_token = get_token_by_alias(token_alias)
        mime_type = GoogleServiceUtil.MIME_TYPES.get(file_type.lower())
        if not mime_type:
            raise ValueError(f"Unsupported file type: {file_type}")
        return GoogleServiceUtil._list_files_by_mime_type(mime_type, access_token)

    @staticmethod
    def _list_files_by_mime_type(mime_type: str, access_token: str) -> List[dict]:
        headers = {"Authorization": f"Bearer {access_token}"}
        query = f"mimeType='{mime_type}'"
        params = {"q": query, "fields": "files(id,name,mimeType)", "pageSize": 100}
        response = requests.get(
            "https://www.googleapis.com/drive/v3/files", headers=headers, params=params
        )
        if response.status_code != 200:
            raise Exception(f"Error getting files: {response.status_code}")
        return response.json().get("files", [])

    @staticmethod
    def create_drive_file(name: str, mime_type: str, token_alias: str) -> dict:
        access_token = get_token_by_alias(token_alias)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        data = {"name": name, "mimeType": mime_type}
        response = requests.post(
            "https://www.googleapis.com/drive/v3/files", headers=headers, json=data
        )
        if response.status_code == 401:
            raise Exception("Unauthorized Operation - Refresh the token.")
        if response.status_code != 200:
            raise Exception(f"Failed to create file: HTTP {response.status_code}")
        return response.json()

    @staticmethod
    def get_drive_file_name(token_alias: str, file_id: str) -> str:
        drive_service = GoogleServiceUtil.get_drive_service(token_alias)
        file_metadata = (
            drive_service.files().get(fileId=file_id, fields="name").execute()
        )
        return file_metadata.get("name", "spreadsheet")

    @staticmethod
    def download_sheet_as_csv(
        token_alias: str, file_id: str, range_: Optional[str] = None
    ) -> str:
        values = GoogleServiceUtil.read_sheet(token_alias, file_id, range_)
        if not values:
            raise Exception("No data found in the specified sheet or range.")

        # Obtener nombre real del archivo desde Drive
        base_name = GoogleServiceUtil.get_drive_file_name(token_alias, file_id)
        sanitized_name = "".join(
            c if c.isalnum() or c in ("_", "-") else "_" for c in base_name
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"temp_{sanitized_name}_{timestamp}.csv"

        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, temp_filename)

        with open(file_path, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            for row in values:
                writer.writerow(row)

        return file_path

    @staticmethod
    def upload_file_simple(
        token_alias: str,
        local_path: str,
        drive_filename: str,
        mime_type: str = "application/octet-stream",
    ) -> dict:
        access_token = get_token_by_alias(token_alias)

        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"File not found: {local_path}")

        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
        headers = {"Authorization": f"Bearer {access_token}"}

        metadata = {"name": drive_filename}

        with open(local_path, "rb") as f:
            files = {
                "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
                "file": (drive_filename, f, mime_type),
            }

            response = requests.post(url, headers=headers, files=files)

        if response.status_code != 200:
            raise Exception(f"Upload failed: {response.status_code} - {response.text}")

        return response.json()

    @staticmethod
    def upload_csv_as_spreadsheet(
        token_alias: str, local_csv_path: str, sheet_name: str
    ) -> dict:
        access_token = get_token_by_alias(token_alias)

        if not os.path.isfile(local_csv_path):
            raise FileNotFoundError(f"File not found: {local_csv_path}")

        endpoint = (
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
        )
        headers = {"Authorization": f"Bearer {access_token}"}

        metadata = {
            "name": sheet_name,
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }

        # Construimos el body multipart de forma segura
        with open(local_csv_path, "rb") as file_data:
            multipart_data = {
                "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
                "file": (os.path.basename(local_csv_path), file_data, "text/csv"),
            }

            response = requests.post(endpoint, headers=headers, files=multipart_data)
            copilot_debug_curl(response.request)
        if response.status_code != 200:
            raise Exception(
                f"Failed to upload CSV as spreadsheet: {response.status_code} - {response.text}"
            )

        return response.json()
