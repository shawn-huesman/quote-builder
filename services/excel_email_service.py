import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from typing import Any, Dict


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
        print("Success! Spreadsheet created.")
        print(f"Spreadsheet ID: {spreadsheet_id}")
        print(f"Direct Link: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")

        return spreadsheet_id

    except HttpError as error:
        print(f"An API error occurred: {error}")
        return None