"""Google Drive utilities for file upload and management."""

import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaInMemoryUpload
import mimetypes
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaInMemoryUpload
import pickle
import logging

logger = logging.getLogger(__name__)

def upload_to_google_drive(file_name, folder_id=None, file_content=None, gc=None, save_dir="resumes"):
    """
    Upload a file to a specific Google Drive folder and return the link.
    
    Args:
        file_name (str): Name of the file to upload
        folder_id (str, optional): Google Drive folder ID to upload to
        file_content (bytes, optional): File content as bytes
        gc: Google client object from get_google_sheets_client
        save_dir (str): Directory where files are stored locally
    
    Returns:
        str: Web view link to the uploaded file, or None if upload failed
    """
    try:
        print(f"🔄 Starting upload of {file_name} to Google Drive...")
        
        # Get credentials
        if gc and hasattr(gc, 'credentials'):
            credentials = gc.credentials
        else:
            # Fall back to the method used in check_folder_exists
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            credentials = None

            if os.path.exists('company_chatbot/token.pickle'):
                with open('company_chatbot/token.pickle', 'rb') as token:
                    credentials = pickle.load(token)

            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('company_chatbot/agentcred.json', SCOPES)
                    credentials = flow.run_local_server(port=0)
                with open('company_chatbot/token.pickle', 'wb') as token:
                    pickle.dump(credentials, token)
        
        # Build the Drive service with the credentials
        drive_service = build('drive', 'v3', credentials=credentials)
        print(f"✅ Drive service created successfully")
        
        # Determine MIME type based on file extension
        if file_name.lower().endswith('.pdf'):
            mime_type = 'application/pdf'
        elif file_name.lower().endswith(('.docx', '.doc')):
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            mime_type = 'application/octet-stream'
        
        # Prepare file metadata
        file_metadata = {
            'name': file_name,
            'mimeType': mime_type
        }
        
        # Add parent folder if provided
        if folder_id:
            file_metadata['parents'] = [folder_id]
            print(f"📁 Uploading to folder ID: {folder_id}")
        else:
            print("⚠️ No folder ID provided, uploading to root Drive")
        
        # Prepare the media for upload
        if file_content is not None:
            # Use in-memory upload if content is provided
            media = MediaInMemoryUpload(
                file_content,
                mimetype=mime_type,
                resumable=True
            )
            print(f"📦 Using in-memory upload for {file_name} ({len(file_content)} bytes)")
        else:
            # Read from disk if no content is provided
            file_path = os.path.join(save_dir, file_name)
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                return None
                
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True
            )
            print(f"📦 Using file upload for {file_path}")
        
        # Create the file in Google Drive
        print(f"📤 Creating file in Google Drive: {file_name}")
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,webViewLink'
        ).execute()
        
        file_id = file.get('id')
        print(f"✅ File created with ID: {file_id}")
        
        # Set permissions to "Anyone with the link can view"
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        drive_service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()
        
        print(f"🔐 Permissions set for file: {file_id}")
        
        # Get the web view link
        web_view_link = file.get('webViewLink')
        print(f"🔗 Google Drive link: {web_view_link}")
        
        # Return the web view link
        return web_view_link
    except Exception as e:
        print(f"❌ Error uploading file to Google Drive: {e}")
        import traceback
        print(traceback.format_exc())
        return None

def check_folder_exists(folder_id, gc=None):
    """
    Check if a folder exists in Google Drive
    
    Args:
        folder_id (str): Google Drive folder ID to check
        gc: Ignored (kept for compatibility)
        
    Returns:
        bool: True if folder exists, False otherwise
    """
    try:
        # Get credentials similar to your original upload function
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = None

        if os.path.exists('company_chatbot/token.pickle'):
            with open('company_chatbot/token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('company_chatbot/agentcred.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('company_chatbot/token.pickle', 'wb') as token:
                pickle.dump(creds, token)
                
        # Build the Drive service with the credentials
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Try to get the folder metadata
        folder = drive_service.files().get(fileId=folder_id).execute()
        
        # Check if it's a folder
        is_folder = folder.get('mimeType') == 'application/vnd.google-apps.folder'
        
        if is_folder:
            print(f"✅ Folder {folder_id} exists and is accessible")
        else:
            print(f"⚠️ ID {folder_id} exists but is not a folder")
            
        return is_folder
    except Exception as e:
        print(f"❌ Error checking folder existence: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def create_folder(folder_name, parent_folder_id=None, gc=None):
    """
    Create a new folder in Google Drive
    
    Args:
        folder_name (str): Name of the folder to create
        parent_folder_id (str, optional): Parent folder ID
        gc: Google client object from get_google_sheets_client
        
    Returns:
        str: ID of the created folder, or None if creation failed
    """
    try:
        # Get credentials
        if gc and hasattr(gc, 'credentials'):
            credentials = gc.credentials
        else:
            # Fall back to the method used in check_folder_exists
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            credentials = None

            if os.path.exists('company_chatbot/token.pickle'):
                with open('company_chatbot/token.pickle', 'rb') as token:
                    credentials = pickle.load(token)

            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('company_chatbot/agentcred.json', SCOPES)
                    credentials = flow.run_local_server(port=0)
                with open('company_chatbot/token.pickle', 'wb') as token:
                    pickle.dump(credentials, token)
        
        # Build the Drive service with the credentials
        drive_service = build('drive', 'v3', credentials=credentials)
        
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]
            
        folder = drive_service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        
        return folder.get('id')
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        return None