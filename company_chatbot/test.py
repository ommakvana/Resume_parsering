from sheet_agent import get_google_sheets_client
from drive_agent import upload_to_google_drive, check_folder_exists

# Test folder ID
FOLDER_ID = "1XdmlQ-v_h7rV319pfLGVdvcLFmNrIbeH"  # Replace with your folder ID

# Get Google client
gc = get_google_sheets_client()

# Check if folder exists
if check_folder_exists(FOLDER_ID, gc):
    # Test upload
    test_file_path = "test.txt"
    with open(test_file_path, "w") as f:
        f.write("This is a test file")
    
    with open(test_file_path, "rb") as f:
        file_content = f.read()
    
    link = upload_to_google_drive(
        file_name="test.txt",
        folder_id=FOLDER_ID,
        file_content=file_content,
        gc=gc
    )
    
    print(f"Test upload result: {link}")
else:
    print("Folder does not exist or is not accessible")