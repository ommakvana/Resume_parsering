"""Entry point for the resume processing script."""

import time
from data_ingestion.email_fetcher import fetch_resumes_from_email

def main():
    """Run the resume processing workflow."""
    print(f"Starting resume processing at {time.ctime()}...")
    print("Will check emails, process each resume immediately, and update Excel file")
    new_files = fetch_resumes_from_email()
    print(f"Total new resumes fetch_resumes_from_emailprocessed: {new_files}")

if __name__ == "__main__":
    main()