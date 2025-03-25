from flask import Flask, render_template, request, jsonify
import os
import time
import shutil
from werkzeug.utils import secure_filename
from data_ingestion.file_processor import process_single_resume, extract_text_from_pdf, extract_text_from_docx, parse_resume
from data_ingestion.config import SAVE_DIR, SPREADSHEET_ID
from Google_work.google_sheet import write_to_google_sheet, get_google_sheets_client
from Google_work.google_drive import upload_to_google_drive
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
TEMP_STORAGE_FOLDER = 'temp_storage'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'rtf', 'txt', 'png', 'jpg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(TEMP_STORAGE_FOLDER):
    os.makedirs(TEMP_STORAGE_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    char_count = len(text)
    estimated_tokens = int(char_count / 4.5)
    estimated_tokens = int(estimated_tokens * 1.2)
    print(f"Estimated tokens for text (length {char_count} chars): {estimated_tokens}")
    return estimated_tokens

def truncate_text(text: str, max_tokens: int) -> str:
    """Truncate text to fit within the max_tokens limit."""
    chars_per_token = 4.5
    max_chars = int(max_tokens * chars_per_token / 1.2)
    if len(text) <= max_chars:
        return text
    truncated_text = text[:max_chars]
    print(f"Truncated text from {len(text)} to {max_chars} characters to fit within {max_tokens} tokens")
    return truncated_text

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'resumes' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('resumes')
    if len(files) > 10:
        return jsonify({'error': 'Maximum 10 resumes allowed'}), 400

    if len(files) == 0:
        return jsonify({'error': 'No valid files selected'}), 400

    parsed_resumes = []
    max_retries = 3
    retry_delay = 60
    max_tokens = 5500

    file_references = {}

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            temp_file_path = os.path.join(TEMP_STORAGE_FOLDER, filename)
            file.save(file_path)

            # Copy the file to the temp storage folder
            shutil.copy(file_path, temp_file_path)

            # Store the filename as a reference
            file_references[filename] = filename

            # Extract text based on file type
            for attempt in range(max_retries):
                try:
                    if filename.lower().endswith('.pdf'):
                        resume_text = extract_text_from_pdf(file_path)
                    else:
                        resume_text = extract_text_from_docx(file_path, advanced_mode=False)

                    estimated_tokens = estimate_tokens(resume_text)
                    if estimated_tokens > max_tokens:
                        print(f"Resume text for {filename} exceeds {max_tokens} tokens, truncating")
                        resume_text = truncate_text(resume_text, max_tokens)

                    parsed_data = parse_resume(resume_text, filename)
                    if 'error' in parsed_data:
                        parsed_data['original_filename'] = filename
                        parsed_resumes.append(parsed_data)
                    else:
                        parsed_data['Date'] = datetime.now().strftime("%d/%m/%Y")
                        parsed_data['original_filename'] = filename  # Add original_filename for successful parses
                        parsed_resumes.append(parsed_data)
                    break
                except Exception as e:
                    if "rate_limit_exceeded" in str(e) and attempt < max_retries - 1:
                        print(f"Rate limit exceeded for {filename}, retrying in {retry_delay} seconds (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        print(f"Error processing {filename}: {e}")
                        parsed_resumes.append({
                            'original_filename': filename,
                            'error': str(e)
                        })
                        break
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)
        else:
            parsed_resumes.append({
                'original_filename': file.filename,
                'error': 'Unsupported file type'
            })

    return jsonify({'resumes': parsed_resumes, 'file_references': file_references})

@app.route('/save', methods=['POST'])
def save_to_sheet():
    data = request.json
    resumes = data.get('resumes', [])
    file_references = data.get('file_references', {})
    if not resumes:
        return jsonify({'error': 'No resumes to save'}), 400

    # Initialize Google Sheets client for Google Drive upload
    gc = get_google_sheets_client()
    success_count = 0

    for resume in resumes:
        try:
            if 'error' not in resume:
                # Get the original filename from the resume data
                filename = resume.get('original_filename', '')
                if not filename:
                    print(f"Skipping resume with missing original_filename: {resume}")
                    continue

                # Check if we have the file reference for this filename
                if filename in file_references:
                    # Retrieve the file from the temp storage folder
                    temp_file_path = os.path.join(TEMP_STORAGE_FOLDER, filename)
                    if os.path.exists(temp_file_path):
                        with open(temp_file_path, 'rb') as f:
                            file_content = f.read()
                        # Upload to Google Drive and get the shareable link
                        print(f"Uploading {filename} to Google Drive")
                        drive_link = upload_to_google_drive(filename, file_content, gc)
                        if drive_link:
                            resume['File Name'] = drive_link
                        else:
                            print(f"Failed to upload {filename} to Google Drive")
                            resume['File Name'] = filename
                        # Remove the temporary file after uploading
                        os.remove(temp_file_path)
                    else:
                        print(f"Temporary file not found for {filename}")
                        resume['File Name'] = filename
                else:
                    print(f"No file reference found for {filename}")
                    resume['File Name'] = filename

                # Remove temporary fields that shouldn't be saved to the sheet
                resume.pop('original_filename', None)

                # Save to Google Sheet with the updated File Name
                print(f"Saving resume to Google Sheet: {resume}")
                write_to_google_sheet(resume, SPREADSHEET_ID)
                success_count += 1
        except Exception as e:
            print(f"Error saving {resume.get('original_filename', 'unknown')}: {e}")

    # Clean up any remaining temporary files
    for filename in file_references:
        temp_file_path = os.path.join(TEMP_STORAGE_FOLDER, filename)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return jsonify({'message': f'Successfully saved {success_count} out of {len(resumes)} resumes'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6600, debug=True)