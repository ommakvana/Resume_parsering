"""Logic for fetching and processing emails with resume attachments."""

import imaplib
import email
import os
import time
import email.utils
import re
import gc
import json
from data_ingestion.utils import get_last_check_time,save_last_check_time
from datetime import datetime, timedelta
from data_ingestion.config import EMAIL, PASSWORD, IMAP_SERVER, SAVE_DIR
from data_ingestion.utils import get_last_check_time,save_last_check_time, extract_ctc_from_body, save_email_metadata
from Google_work.google_sheet import get_google_sheets_client
from data_ingestion.file_processor import process_single_resume
from Google_work.google_drive import upload_to_google_drive
from data_ingestion.utils import extract_experience_from_body

def fetch_resumes_from_email():
    """Fetch new resumes from email and process them immediately."""
    gc = get_google_sheets_client()
    # spreadsheet_id = "1abJoq2JX3CHDu5pwH1xt6uMgADDekxxmzlW8DQIzFmI"
    max_retries = 15

    for attempt in range(max_retries):
        try:
            with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
                mail.login(EMAIL, PASSWORD)
                new_files = 0

                print("📂 Checking Inbox...")
                mail.select("inbox")
                new_files += process_emails(mail)

                status, folders = mail.list()
                available_folders = [folder.decode().split(' "/" ')[-1] for folder in folders]
                subfolders_to_check = ["Junk",
                                   "INBOX/Important", "INBOX/Unsorted", "INBOX/JobApplications", 
                                   "INBOX/Naukri.com", "INBOX/Unnecessary", "Drafts"]

                for folder in subfolders_to_check:
                    if folder in available_folders:
                        print(f"📂 Checking {folder}...")
                        mail.select(folder)
                        new_files += process_emails(mail)
                    else:
                        print(f"⚠️ Skipping {folder} (Not Found)")

                print(f"🎉 Total new resumes saved and processed: {new_files}")
                save_last_check_time()  # Moved to utils.py if needed
                return new_files

        except Exception as e:
            print(f"❌ Error: {e}")
            return 0

def process_emails(mail):
    """Process emails and handle resume attachments."""
    import pytz
    
    new_files = 0
    ist = pytz.timezone("Asia/Kolkata")
    
    last_check_time = get_last_check_time()
    if last_check_time.tzinfo is None:
        last_check_time_ist = ist.localize(last_check_time)
    else:
        last_check_time_ist = last_check_time
    
    last_check_time_utc = last_check_time_ist.astimezone(pytz.UTC)
    since_date = last_check_time_utc.strftime("%d-%b-%Y")
    print(f"📅 Checking all emails since {since_date} (IST: {last_check_time_ist.strftime('%d-%b-%Y %H:%M:%S %Z')})...")
    
    search_cmd = f'(SINCE "{since_date}")'
    print(f"🔍 Executing IMAP search command: {search_cmd}")

    destination_folder = "INBOX/Processed_Resumes"

    try:
        # Check if the destination folder exists, if not create it
        status, folder_list = mail.list()
        if status != "OK":
            print(f"❌ Failed to list folders: {status}")
            return new_files
            
        folder_exists = False
        for folder_info in folder_list:
            if folder_info:
                folder_parts = folder_info.decode().split(' "/"')
                if len(folder_parts) > 1 and destination_folder in folder_parts[1]:
                    folder_exists = True
                    break
                    
        if not folder_exists:
            print(f"📁 Creating folder: {destination_folder}")
            status, create_response = mail.create(destination_folder)
            if status != "OK":
                print(f"❌ Failed to create folder {destination_folder}: {create_response}")
                # Continue processing but won't be able to move emails
            else:
                print(f"✅ Folder {destination_folder} created successfully")
                
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)
            
        status, messages = mail.search(None, search_cmd)
        if status != "OK":
            print(f"❌ Search failed with status: {status}, response: {messages}")
            return new_files
            
        if not messages[0]:
            print(f"✅ No new emails since {since_date} (IST: {last_check_time_ist.strftime('%d-%b-%Y %H:%M:%S %Z')}).")
            return new_files
            
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        processed_files = {}
        processed_files_path = os.path.join(SAVE_DIR, "processed_files.json")
        
        if os.path.exists(processed_files_path):
            try:
                with open(processed_files_path, 'r') as f:
                    processed_files = json.load(f)
            except:
                print("⚠️ Could not load processed files history")
                
        for msg_num in messages[0].split():
            status, msg_data = mail.fetch(msg_num, "(INTERNALDATE RFC822)")
            if status != "OK":
                print(f"❌ Fetch failed for message {msg_num}: {msg_data}")
                continue
                
            # Flag to track if this email should be moved after processing
            email_processed = False
                
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    email_date = None
                    for part in response_part:
                        if isinstance(part, bytes) and part.startswith(b'INTERNALDATE'):
                            date_str = part.decode('utf-8')
                            match = re.search(r'"([^"]+)"', date_str)
                            if match:
                                try:
                                    date_str = match.group(1)
                                    internal_date = email.utils.parsedate_to_datetime(date_str)
                                    if internal_date.tzinfo is None:
                                        internal_date = pytz.UTC.localize(internal_date)
                                    internal_date_ist = internal_date.astimezone(ist)
                                    email_date = internal_date_ist.strftime("%d/%m/%Y")
                                    print(f"📅 Email received date: {email_date} (IST)")
                                except Exception as e:
                                    print(f"⚠️ Error parsing internal date: {e}")
                                    
                    msg = email.message_from_bytes(response_part[1])
                    
                    if not email_date and msg["date"]:
                        try:
                            parsed_date = email.utils.parsedate_to_datetime(msg["date"])
                            if parsed_date.tzinfo is None:
                                parsed_date = pytz.UTC.localize(parsed_date)
                            parsed_date_ist = parsed_date.astimezone(ist)
                            email_date = parsed_date_ist.strftime("%d/%m/%Y")
                            print(f"📅 Using header date: {email_date} (IST)")
                        except Exception as e:
                            print(f"⚠️ Error parsing header date: {e}")
                            
                    if not email_date:
                        now_ist = datetime.now(pytz.UTC).astimezone(ist)
                        email_date = now_ist.strftime("%d/%m/%Y")
                        print(f"⚠️ No date found, using today: {email_date} (IST)")
                        
                    sender = msg["from"]
                    subject = msg["subject"]
                    print(f"📬 Processing: {subject} from {sender}")
                    
                    email_body = ""
                    html_body = ""
                    
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                try:
                                    email_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                except:
                                    try:
                                        email_body = part.get_payload(decode=True).decode('latin-1', errors='ignore')
                                    except:
                                        email_body = str(part.get_payload(decode=True))
                            elif content_type == "text/html":
                                try:
                                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                except:
                                    try:
                                        html_body = part.get_payload(decode=True).decode('latin-1', errors='ignore')
                                    except:
                                        html_body = str(part.get_payload(decode=True))
                    else:
                        try:
                            email_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            try:
                                email_body = msg.get_payload(decode=True).decode('latin-1', errors='ignore')
                            except:
                                email_body = str(msg.get_payload(decode=True))
                                
                    if (not email_body or len(email_body) < 50) and html_body:
                        email_body = html_body
                        
                    print(f"📄 Email Body:\n{email_body[:500]}...")
                    
                    experience_from_email = extract_experience_from_body(email_body)
                    if experience_from_email:
                        print(f"👨‍💼 Found experience in email body: {experience_from_email} years")
                        
                    ctc_info = extract_ctc_from_body(email_body)
                    if ctc_info:
                        print(f"💰 Found CTC in email body: {ctc_info}")
                        
                    saved_files = []
                    file_links = {}
                    attachment_processed = False
                    
                    attachments = [part for part in msg.walk() if part.get_content_disposition() == "attachment"]
                    
                    for part in attachments:
                        filename = part.get_filename()
                        if not filename or not filename.lower().endswith((".pdf", ".docx", ".doc")):
                            continue
                            
                        if attachment_processed:
                            print(f"⏩ Skipping attachment: {filename} (valid resume already processed for this email)")
                            continue
                            
                        file_content = part.get_payload(decode=True)
                        file_path = os.path.join(SAVE_DIR, filename)
                        file_date = None
                        
                        if filename in processed_files:
                            file_date_str = processed_files[filename]
                            try:
                                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                            except:
                                file_date = None
                                
                        if file_date and (file_date == today or file_date == yesterday):
                            print(f"⏩ Skipping: {filename} (already processed on {file_date.strftime('%Y-%m-%d')})")
                            continue
                            
                        with open(file_path, "wb") as f:
                            f.write(file_content)
                            
                        print(f"✅ Saved: {file_path}")
                        processed_files[filename] = today.strftime("%Y-%m-%d")
                            
                        file_link = upload_to_google_drive(filename, file_content, gc)
                        if file_link:
                            file_links[filename] = file_link
                            print(f"🔗 Generated link for {filename}: {file_link}")
                            
                        metadata = {"email_date": email_date}
                        if ctc_info:
                            metadata["ctc_from_email"] = ctc_info
                        if file_link:
                            metadata["drive_link"] = file_link
                        if experience_from_email:
                            metadata["experience_from_email"] = experience_from_email
                            
                        resume_data = process_single_resume(filename, file_link, email_date)
                        print(f"ℹ️ Resume data extracted: {resume_data}")
                        
                        save_email_metadata(filename, metadata)
                        saved_files.append(filename)
                        new_files += 1
                        
                        # Set the flag to move this email after processing
                        email_processed = True
                        
                        # Fallback: If resume_data is None but we have content (like PDF extraction), assume it's valid
                        if resume_data is None and filename.lower().endswith(".pdf"):
                            attachment_processed = True
                            print(f"✅ Attachment {filename} assumed as resume (PDF with content extracted), skipping remaining attachments")
                            break
                            
                        # Normal case: Check for required fields
                        elif resume_data and all(
                            field in resume_data and resume_data[field] not in [None, "", [], {}]
                            for field in ['name', 'experience', 'skills']
                        ):
                            attachment_processed = True
                            print(f"✅ Attachment {filename} contains all required resume data, skipping remaining attachments")
                            break
            
            # Mark the email as seen
            mail.store(msg_num, '+FLAGS', '\\Seen')
            
            # If we processed an attachment for this email, move it to the destination folder
            if email_processed:
                try:
                    # Copy the email to the destination folder
                    result, data = mail.copy(msg_num, destination_folder)
                    if result == "OK":
                        # Mark the original email for deletion
                        mail.store(msg_num, '+FLAGS', '\\Deleted')
                        print(f"📁 Email moved to {destination_folder} folder and marked for deletion from inbox")
                    else:
                        print(f"⚠️ Failed to move email to {destination_folder} folder: {data}")
                except Exception as e:
                    print(f"❌ Error moving email to folder: {str(e)}")
        
        # Expunge deleted messages to permanently remove them
        mail.expunge()
        print("🗑️ Expunged deleted messages from inbox")
        
        try:
            with open(processed_files_path, 'w') as f:
                json.dump(processed_files, f)
        except:
            print("⚠️ Could not save processed files history")
            
    except Exception as e:
        print(f"❌ Error during email processing: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
    return new_files