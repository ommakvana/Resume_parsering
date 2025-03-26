import imaplib
import email

# Email credentials
EMAIL = "om.makvana@logbinary.com"
PASSWORD = "Om@LogBinary"
IMAP_SERVER = "imap.secureserver.net"
IMAP_PORT = 993
DEST_FOLDER = "INBOX/Test"  # Target folder

# Connect to GoDaddy IMAP
mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
mail.login(EMAIL, PASSWORD)

# Select INBOX
mail.select("INBOX")

# Search for unread emails
status, email_ids = mail.search(None, '(UNSEEN)')
email_ids = email_ids[0].split()

for e_id in email_ids:
    # Fetch email data
    _, msg_data = mail.fetch(e_id, "(RFC822)")
    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    # Check if the email has a resume
    has_resume = False
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            filename = part.get_filename()
            if filename and (filename.endswith(".pdf") or filename.endswith(".docx")):
                has_resume = True
                break

    if has_resume:
        print(f"Moving email {e_id} to '{DEST_FOLDER}'")

        # Copy email to "JobApplications"
        mail.copy(e_id, DEST_FOLDER)

        # Mark email as deleted from INBOX
        mail.store(e_id, '+FLAGS', '\\Deleted')

# Expunge deleted emails (permanently remove them from INBOX)
mail.expunge()

# Logout
mail.logout()
print("Emails successfully moved!")
