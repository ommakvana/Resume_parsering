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
    new_files = 0

    last_check_time = get_last_check_time()

    if last_check_time.date() == datetime.now().date():
        since_date = datetime.now().strftime("%d-%b-%Y")
        print(f"📅 Checking emails from today at {last_check_time.strftime('%H:%M:%S')} to now...")
    else:
        since_date = last_check_time.strftime("%d-%b-%Y")
        print(f"📅 Checking emails from {since_date} to today...")

    search_cmd = f'(SINCE "{since_date}")'
    print(f"🔍 Executing IMAP search command: {search_cmd}")

    try:
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)

        # Search for unread emails between yesterday and today
        status, messages = mail.search(None, search_cmd)

        if status != "OK":
            print(f"❌ Search failed with status: {status}, response: {messages}")
            return new_files

        if not messages[0]:
            print(f"✅ No new emails since {since_date}.")
            return new_files

        # Keep track of processed files with dates
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        processed_files = {}
        
        # Load previously processed files if you want to maintain state between runs
        processed_files_path = os.path.join(SAVE_DIR, "processed_files.json")
        if os.path.exists(processed_files_path):
            try:
                with open(processed_files_path, 'r') as f:
                    processed_files = json.load(f)
            except:
                print("⚠️ Could not load processed files history")

        # Process each email
        for msg_num in messages[0].split():
            status, msg_data = mail.fetch(msg_num, "(INTERNALDATE RFC822)")
            if status != "OK":
                print(f"❌ Fetch failed for message {msg_num}: {msg_data}")
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    email_date = None
                    # internal_date = None
                    for part in response_part:
                        if isinstance(part, bytes) and part.startswith(b'INTERNALDATE'):
                            date_str = part.decode('utf-8')
                            match = re.search(r'"([^"]+)"', date_str)
                            if match:
                                try:
                                    date_str = match.group(1)
                                    internal_date = email.utils.parsedate_to_datetime(date_str)
                                    email_date = internal_date.strftime("%d/%m/%Y")
                                    print(f"📅 Email received date: {email_date}")
                                except Exception as e:
                                    print(f"⚠️ Error parsing internal date: {e}")

                        msg = email.message_from_bytes(response_part[1])
                        if not email_date and msg["date"]:
                            try:
                                parsed_date = email.utils.parsedate_to_datetime(msg["date"])
                                email_date = parsed_date.strftime("%d/%m/%Y")
                                print(f"📅 Using header date: {email_date}")
                            except Exception as e:
                                print(f"⚠️ Error parsing header date: {e}")

                        if not email_date:
                            email_date = datetime.now().strftime("%d/%m/%Y")
                            print(f"⚠️ No date found, using today: {email_date}")

                    sender = msg["from"]
                    subject = msg["subject"]
                    print(f"📬 Processing: {subject} from {sender}")

                    email_body = ""
                    html_body = ""
                    experience_from_email = extract_experience_from_body(email_body)
                    if experience_from_email:
                        print(f"👨‍💼 Found experience in email body: {experience_from_email} years")
                        
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

                    ctc_info = extract_ctc_from_body(email_body)
                    if ctc_info:
                        print(f"💰 Found CTC in email body: {ctc_info}")

                    saved_files = []
                    file_links = {}
                    for part in msg.walk():
                        if part.get_content_disposition() == "attachment":
                            filename = part.get_filename()
                            if filename and filename.lower().endswith((".pdf", ".docx", ".doc", ".rtf", ".txt", ".png", ".jpg")):
                                file_content = part.get_payload(decode=True)
                                file_path = os.path.join(SAVE_DIR, filename)
                                
                                # Check if this file has been processed before
                                file_date = None
                                if filename in processed_files:
                                    file_date_str = processed_files[filename]
                                    try:
                                        file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                                    except:
                                        file_date = None
                                
                                # Skip if the file was already processed today
                                if file_date and (file_date == today or file_date == yesterday):
                                    print(f"⏩ Skipping: {filename} (already processed on {file_date.strftime('%Y-%m-%d')})")
                                    continue
                                
                                # Process the file if it's either not seen before or not processed today
                                with open(file_path, "wb") as f:
                                    f.write(file_content)
                                print(f"✅ Saved: {file_path}")
                                
                                # Update processed files record
                                processed_files[filename] = today.strftime("%Y-%m-%d")
                                
                                # [Rest of your existing attachment processing code...]
                                file_link = upload_to_google_drive(filename, file_content, gc)
                                if file_link:
                                    file_links[filename] = file_link
                                    print(f"🔗 Generated link for {filename}: {file_link}")

                                metadata = {"email_date": email_date}
                                if ctc_info:
                                    metadata["ctc_from_email"] = ctc_info
                                if file_link:
                                    metadata["drive_link"] = file_link
                                    file_links[filename] = file_link
                                if experience_from_email:  
                                    metadata["experience_from_email"] = experience_from_email

                                save_email_metadata(filename, metadata)
                                saved_files.append(filename)
                                new_files += 1
                                process_single_resume(filename, file_link, email_date)
                
            mail.store(msg_num, '+FLAGS', '\\Seen')
            
        # Save the updated processed files record
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