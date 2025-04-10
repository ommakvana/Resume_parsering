"""Utilities for interacting with Google Sheets."""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os
from datetime import datetime

def get_google_sheets_client():
    """Initialize and return a Google Sheets client."""
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

    return gspread.authorize(creds)


def is_file_in_sheet(gc, spreadsheet_id, file_name_or_link):
    """Check if a file has already been processed in the spreadsheet."""
    try:
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.sheet1
        all_values = worksheet.get_all_values()
        if not all_values:
            return False

        header_row_idx = 0
        file_name_col_idx = 0
        for idx, row in enumerate(all_values):
            if 'File Name' in row:
                header_row_idx = idx
                file_name_col_idx = row.index('File Name')
                break

        if file_name_col_idx == 0 and 'File Name' not in all_values[header_row_idx]:
            col_a_values = [row[0] for row in all_values[header_row_idx+1:] if row and row[0]]
            return file_name_or_link in col_a_values

        file_values = []
        for i in range(header_row_idx+1, len(all_values)):
            if len(all_values[i]) > file_name_col_idx and all_values[i][file_name_col_idx]:
                file_values.append(all_values[i][file_name_col_idx])
        
        # Check if either the file name or the Drive link exists in the column
        return file_name_or_link in file_values

    except Exception as e:
        print(f"Error checking if file exists in sheet: {e}")
        return False

def write_to_google_sheet(parsed_data, spreadsheet_id):
    """Write parsed resume data to Google Sheets."""
    try:
        gc = get_google_sheets_client()
        
        # Ensure we use Drive Link for File Name if available
        if "Drive Link" in parsed_data and parsed_data["Drive Link"]:
            parsed_data["File Name"] = parsed_data["Drive Link"]
            
        file_name = parsed_data.get("File Name", "Unknown")
        
        if is_file_in_sheet(gc, spreadsheet_id, file_name):
            print(f"⏩ Skipping: {file_name} (already in Google Sheet)")
            return False
            
        sh = gc.open_by_key(spreadsheet_id)
        worksheet = sh.sheet1
        all_values = worksheet.get_all_values()
        
        if "Date" not in parsed_data:
            today = datetime.now().strftime("%d/%m/%Y")
            parsed_data["Date"] = today
            
        full_headers = [
            "Date", "Name", "Email Id", "Contact No", "Current Location", "Category",
            "Total Experience", "Designation", "Skills", "CTC info",
            "No of companies worked with till today", "Last company worked with", "Loyalty %", "File Name"
        ]
        
        if not all_values:
            print("DEBUG - Sheet is empty, setting headers")
            worksheet.update('A1', [full_headers])
            print(f"DEBUG - Headers set to: {full_headers}")
            worksheet.format('A1:Z1', {"textFormat": {"bold": True}})
            row_to_insert = 2
        else:
            header_row_idx = 0
            for idx, row in enumerate(all_values):
                if 'Date' in row or 'File Name' in row or 'Name' in row or 'Email Id' in row:
                    header_row_idx = idx
                    break
                    
            headers = all_values[header_row_idx]
            headers_updated = False
            for header in full_headers:
                if header not in headers:
                    headers.append(header)
                    headers_updated = True
            if headers_updated:
                worksheet.update(f'A{header_row_idx+1}', [headers])
                print(f"DEBUG - Updated headers to: {headers}")
                worksheet.format(f'A{header_row_idx+1}:Z{header_row_idx+1}', {"textFormat": {"bold": True}})
                
            row_to_insert = header_row_idx + 2
            worksheet.insert_row([""], row_to_insert)
            
        row_data = []
        for header in headers:
            if not header.strip():
                row_data.append("")
                continue
            row_data.append(parsed_data.get(header, ""))
            
        worksheet.update(f'A{row_to_insert}', [row_data])
        print(f"✅ Added {file_name} to Google Sheet at row {row_to_insert}")
        return True
        
    except Exception as e:
        print(f"❌ Error writing to Google Sheet: {e}")
        import traceback
        print(traceback.format_exc())
        return False