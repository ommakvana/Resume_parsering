from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
from data_ingestion.file_processor import process_single_resume, extract_text_from_pdf, extract_text_from_docx, parse_resume
from data_ingestion.config import SAVE_DIR, SPREADSHEET_ID
from Google_work.google_sheet import write_to_google_sheet
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'rtf', 'txt', 'png', 'jpg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

    parsed_resumes = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Extract text based on file type
            try:
                if filename.lower().endswith('.pdf'):
                    resume_text = extract_text_from_pdf(file_path)
                else:
                    resume_text = extract_text_from_docx(file_path, advanced_mode=False)
                
                # Parse the resume
                parsed_data = parse_resume(resume_text, filename)
                parsed_data['File Name'] = filename
                parsed_data['Date'] = datetime.now().strftime("%d/%m/%Y")
                parsed_resumes.append(parsed_data)
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                parsed_resumes.append({'File Name': filename, 'error': str(e)})

            # Clean up uploaded file
            os.remove(file_path)

    return jsonify({'resumes': parsed_resumes})

@app.route('/save', methods=['POST'])
def save_to_sheet():
    resumes = request.json.get('resumes', [])
    if not resumes:
        return jsonify({'error': 'No resumes to save'}), 400

    success_count = 0
    for resume in resumes:
        try:
            if 'error' not in resume:
                write_to_google_sheet(resume, SPREADSHEET_ID)
                success_count += 1
        except Exception as e:
            print(f"Error saving {resume.get('File Name', 'unknown')}: {e}")

    return jsonify({'message': f'Successfully saved {success_count} out of {len(resumes)} resumes'})

if __name__ == '__main__':
    app.run(debug=True)