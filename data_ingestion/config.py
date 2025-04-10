"""Configuration settings and constants for the resume processor."""

import os

# Email settings
LAST_CHECK_FILE = "last_email_check.pickle"

USE_GMAIL = False
if USE_GMAIL:
    EMAIL = "om.logbinary@gmail.com"
    PASSWORD = "bght egln bgok mrsu"  # Google App Password
    IMAP_SERVER = "imap.gmail.com"
# else:
#     EMAIL = "hr@logbinary.com"
#     PASSWORD = "HR@logbinary"  # GoDaddy password
#     IMAP_SERVER = "imap.secureserver.net"
else:
    EMAIL="om.makvana@logbinary.com"
    PASSWORD="Om@LogBinary" # GoDaddy password
    IMAP_SERVER="imap.secureserver.net"

SPREADSHEET_ID = "1moOssMtT96cifsWtDLpXRae_7v0yMtjwDBRCgJtyzPM"
DRIVE_FOLDER_ID = "1U1xy6XZ3GncGBaYNiKmWTn-aDc9pxBIx"
# File system settings
SAVE_DIR = "hr_mail_testing"
os.makedirs(SAVE_DIR, exist_ok=True)

# Groq API keys
API_KEYS = [
    "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",  # testing
    "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",  # om makvana
    "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",  # om work
    "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",  # dev logbinary
    "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",  # om.logbinary
    "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",  # vinod bhai
    "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",  # clg
    "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",  # sen TenZ
    "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",  # unknown
]