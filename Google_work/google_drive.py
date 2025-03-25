"""Utilities for uploading files to Google Drive."""

import os
import pickle
import mimetypes
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaInMemoryUpload
from data_ingestion.config import DRIVE_FOLDER_ID

def upload_to_google_drive(file_path, file_content, gc):
    """Upload a file to Google Drive and return its shareable link."""
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = None

        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credential.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        drive_client = build('drive', 'v3', credentials=creds)
        file_name = os.path.basename(file_path)
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]
        }

        media = MediaInMemoryUpload(
            file_content,
            mimetype=mimetypes.guess_type(file_name)[0],
            resumable=True
        )

        file = drive_client.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,webViewLink'
        ).execute()

        file_id = file.get('id')
        file_link = file.get('webViewLink')

        permission = {
            'type': 'anyone',
            'role': 'reader',
            'allowFileDiscovery': False
        }
        drive_client.permissions().create(fileId=file_id, body=permission).execute()

        print(f"✅ Uploaded to Google Drive: {file_name} (ID: {file_id})")
        return file_link

    except Exception as e:
        print(f"❌ Error uploading to Google Drive: {e}")
        import traceback
        print(traceback.format_exc())
        return None