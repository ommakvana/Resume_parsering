"""Utility functions for the resume processor."""

import os
import json
import re
import pickle
from datetime import datetime, timedelta
from data_ingestion.config import SAVE_DIR, LAST_CHECK_FILE

def get_last_check_time():
    """Get the timestamp of the last email check."""
    if os.path.exists(LAST_CHECK_FILE):
        try:
            with open(LAST_CHECK_FILE, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error reading last check time: {e}")
    return datetime.now()

def save_last_check_time():
    """Save the current time as the last email check timestamp."""
    try:
        with open(LAST_CHECK_FILE, 'wb') as f:
            pickle.dump(datetime.now(), f)
        print(f"✅ Updated last check time to {datetime.now()}")
    except Exception as e:
        print(f"Error saving last check time: {e}")

def extract_ctc_from_body(email_body):
    """Extract CTC information from email body."""
    if not email_body:
        return None

    bullet_patterns = [
        r'Current CTC:?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|L|LPA|Cr)',
        r'Expected CTC:?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|L|LPA|Cr)',
        r'CTC:?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|L|LPA|Cr)',
    ]

    for pattern in bullet_patterns:
        matches = re.findall(pattern, email_body, re.IGNORECASE)
        if matches:
            if len(matches) > 1 and "Expected CTC" in email_body:
                for idx, match in enumerate(re.finditer(pattern, email_body, re.IGNORECASE)):
                    context = email_body[max(0, match.start()-20):min(match.end()+20, len(email_body))]
                    if "expected" in context.lower():
                        return float(match.group(1))
            return float(matches[0])

    general_patterns = [
        r'package[\s:]*(?:is|of)?[\s:]*(\d+(?:\.\d+)?)\s*(?:lakhs?|L|LPA|Cr)',
        r'salary[\s:]*(?:is|of)?[\s:]*(\d+(?:\.\d+)?)\s*(?:lakhs?|L|LPA|Cr)',
        r'(?:offering|offered)[\s:]*(?:a)?[\s:]*(\d+(?:\.\d+)?)\s*(?:lakhs?|L|LPA|Cr)',
        r'(?:^|\s)(\d+(?:\.\d+)?)\s*(?:lakhs?|L|LPA|Cr)(?:\s|$)',
    ]

    for pattern in general_patterns:
        matches = re.findall(pattern, email_body, re.IGNORECASE)
        if matches:
            return float(matches[0])
    return None

def extract_experience_from_body(email_body):
    """Extract experience information from email body."""
    # Convert to lowercase and clean up newlines for better regex matching
    clean_body = email_body.lower().replace('\n', ' ').replace('\r', ' ')
    
    # Define regex patterns for various experience formats
    patterns = [
        r'(?:total|overall|work|professional)\s+experience\s*(?:of|:|\-)?\s*(\d+\.?\d*)\s*(?:years|yrs)',
        r'(?:having|with|possess(?:ing)?)\s+(\d+\.?\d*)\s*(?:years|yrs)(?:\s+of)?\s+experience',
        r'experience\s*(?:of|:|\-)?\s*(\d+\.?\d*)\s*(?:years|yrs)',
        r'(\d+\.?\d*)\s*(?:years|yrs)(?:\s+of)?\s+experience',
        r'experience\s*:\s*(\d+\.?\d*)\s*(?:years|yrs)',
    ]
    
    # Try each pattern
    for pattern in patterns:
        matches = re.findall(pattern, clean_body)
        if matches:
            # Take the first match and convert to float
            try:
                experience = float(matches[0])
                return experience
            except ValueError:
                continue
    
    return None

def save_email_metadata(filename, metadata):
    """Save metadata associated with a file."""
    metadata_file = os.path.splitext(filename)[0] + "_metadata.json"
    metadata_path = os.path.join(SAVE_DIR, metadata_file)

    existing_metadata = {}
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                existing_metadata = json.load(f)
        except Exception as e:
            print(f"Warning: Could not read existing metadata: {e}")

    existing_metadata.update(metadata)

    try:
        with open(metadata_path, 'w') as f:
            json.dump(existing_metadata, f, indent=2)
    except Exception as e:
        print(f"Error saving metadata: {e}")