import io
import re

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from typing import Any, Dict

import logging
logger = logging.getLogger(__name__)


def share_folder_via_email(
        excel_key: Dict[str, Any],
        delegate_user: str,
        folder_id: str,
        email_address: str,
        role: str = "writer",
        custom_message: str = None
) -> bool:
    try:
        scopes = ['https://www.googleapis.com/auth/drive']

        credentials = service_account.Credentials.from_service_account_info(
            excel_key, scopes=scopes
        )
        credentials = credentials.with_subject(delegate_user)

        drive_service = build('drive', 'v3', credentials=credentials)

        permission_metadata = {
            'type': 'user',
            'role': role,
            'emailAddress': email_address
        }

        request = drive_service.permissions().create(
            fileId=folder_id,
            body=permission_metadata,
            sendNotificationEmail=True,
            supportsAllDrives=True,
            fields='id'
        )

        if custom_message:
            request.uri += f"&emailMessage={requests.utils.quote(custom_message)}"

        permission = request.execute()

        print(f"Successfully shared folder {folder_id} with {email_address}.")
        return True

    except HttpError as error:
        print(f"An API error occurred while sharing: {error}")
        return False


def upload_excel_buffer_to_google_drive(
    excel_buffer: io.BytesIO,
    excel_key: Dict[str, Any],
    delegate_user: str,
    folder_id: str,
    title: str = "Quote Export",
) -> str:
    excel_buffer.seek(0)

    scopes = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets',
    ]
    credentials = service_account.Credentials.from_service_account_info(
        excel_key, scopes=scopes
    )
    if delegate_user:
        credentials = credentials.with_subject(delegate_user)

    drive_service = build('drive', 'v3', credentials=credentials)

    file_metadata = {
        'name': title,
        'parents': [folder_id],
        'mimeType': 'application/vnd.google-apps.spreadsheet',
    }

    media = MediaIoBaseUpload(
        excel_buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        resumable=True,
    )

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        supportsAllDrives=True,
        fields='id',
    ).execute()

    spreadsheet_id = file.get('id')
    return spreadsheet_id


def sync_workspace_folders(
    excel_key: Dict[str, Any],
    delegate_user: str,
    parent_folder_id: str,
    workspaces: Dict[str, Dict[str, Any]],
):
    try:
        scopes = ["https://www.googleapis.com/auth/drive"]

        credentials = service_account.Credentials.from_service_account_info(
            excel_key, scopes=scopes
        )
        credentials = credentials.with_subject(delegate_user)

        drive_service = build("drive", "v3", credentials=credentials)

        query = (
            f"'{parent_folder_id}' in parents and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"trashed = false"
        )

        results = (
            drive_service.files()
            .list(
                q=query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields="files(id, name)",
            )
            .execute()
        )

        existing_files = results.get("files", [])

        existing_folders = {}
        for file in existing_files:
            folder_name = file.get("name", "")
            match = re.search(r"\[(.*?)\]$", folder_name)
            if match:
                ws_id = match.group(1)
                existing_folders[ws_id] = {
                    "drive_id": file.get("id"),
                    "current_name": folder_name,
                }

        for ws_id, ws_data in workspaces.items():
            ws_name = ws_data.get("name", "Workspace")
            target_folder_name = f"{ws_name} [{ws_id}]"

            if ws_id in existing_folders:
                drive_id = existing_folders[ws_id]["drive_id"]
                current_name = existing_folders[ws_id]["current_name"]

                if current_name != target_folder_name:
                    drive_service.files().update(
                        fileId=drive_id,
                        body={"name": target_folder_name},
                        supportsAllDrives=True,
                    ).execute()
                    logger.info(
                        f"Updated folder name for ID {ws_id}: '{current_name}' -> '{target_folder_name}'"
                    )
                else:
                    logger.info(f"Folder already up to date: '{target_folder_name}'")

            else:
                file_metadata = {
                    "name": target_folder_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_folder_id],
                }

                new_folder = (
                    drive_service.files()
                    .create(
                        body=file_metadata,
                        supportsAllDrives=True,
                        fields="id",
                    )
                    .execute()
                )
                logger.info(
                    f"Created folder: '{target_folder_name}' (ID: {new_folder.get('id')})"
                )

    except HttpError as error:
        logger.error(f"An API error occurred: {error}")


def get_folder_id_by_workspace_id(
    excel_key: Dict[str, Any],
    delegate_user: str,
    parent_folder_id: str,
    workspace_id: str | int
) -> str | None:
    try:
        scopes = ['https://www.googleapis.com/auth/drive']

        credentials = service_account.Credentials.from_service_account_info(excel_key, scopes=scopes)
        credentials = credentials.with_subject(delegate_user)

        drive_service = build('drive', 'v3', credentials=credentials)

        query = (
            f"'{parent_folder_id}' in parents and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"name contains '[{workspace_id}]' and "
            f"trashed = false"
        )

        results = drive_service.files().list(
            q=query,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id, name)"
        ).execute()

        files = results.get('files', [])

        if not files:
            logger.info(f"No folder found for workspace ID: {workspace_id}")
            return None

        folder_id = files[0].get('id')
        return folder_id

    except HttpError as error:
        logger.info(f"An API error occurred: {error}")
        return None


def create_spreadsheet_in_folder(excel_key: Dict[str, Any], delegate_user: str, folder_id: str, title: str):
    try:
        scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]

        credentials = service_account.Credentials.from_service_account_info(excel_key, scopes=scopes)
        credentials = credentials.with_subject(delegate_user)

        drive_service = build('drive', 'v3', credentials=credentials)

        file_metadata = {
            'name': title,
            'mimeType': 'application/vnd.google-apps.spreadsheet',
            'parents': [folder_id]
        }

        file = drive_service.files().create(
            body=file_metadata,
            supportsAllDrives=True,
            fields='id'
        ).execute()

        spreadsheet_id = file.get('id')
        logger.info("Success! Spreadsheet created.")
        logger.info(f"Spreadsheet ID: {spreadsheet_id}")
        logger.info(f"Direct Link: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")

        return spreadsheet_id

    except HttpError as error:
        logger.info(f"An API error occurred: {error}")
        return None