from flask import Flask, render_template, request, jsonify, url_for
import os
import time
import shutil
import threading
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, BadSignature
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from data_ingestion.file_processor import process_single_resume, extract_text_from_pdf, extract_text_from_docx, parse_resume
from data_ingestion.config import SAVE_DIR, SPREADSHEET_ID
from Google_work.google_sheet import write_to_google_sheet, get_google_sheets_client
from Google_work.google_drive import upload_to_google_drive

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your-secure-secret-key-here'
UPLOAD_FOLDER = 'uploads'
TEMP_STORAGE_FOLDER = 'temp_storage'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'rtf', 'txt', 'png', 'jpg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# Ensure directories exist
for folder in [UPLOAD_FOLDER, TEMP_STORAGE_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# SQLite database setup
engine = create_engine('sqlite:///resumes.db', echo=True)
Base = declarative_base()

class Resume(Base):
    __tablename__ = 'resumes'
    id = Column(Integer, primary_key=True)
    ip_address = Column(String)
    filename = Column(String)
    token = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# URL-safe serializer
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Locks
sheet_lock = threading.Lock()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def estimate_tokens(text: str) -> int:
    char_count = len(text)
    estimated_tokens = int(char_count / 4.5 * 1.2)
    print(f"Estimated tokens for text (length {char_count} chars): {estimated_tokens}")
    return estimated_tokens

def truncate_text(text: str, max_tokens: int) -> str:
    chars_per_token = 4.5
    max_chars = int(max_tokens * chars_per_token / 1.2)
    if len(text) <= max_chars:
        return text
    truncated_text = text[:max_chars]
    print(f"Truncated text from {len(text)} to {max_chars} characters to fit within {max_tokens} tokens")
    return truncated_text

def generate_encrypted_token():
    data = {'created_at': datetime.now().isoformat()}
    return serializer.dumps(data)

def validate_token(token):
    try:
        serializer.loads(token)
        return True
    except BadSignature:
        return False

def has_ip_submitted(token, ip_address):
    session = Session()
    result = session.query(Resume).filter_by(token=token, ip_address=ip_address).first()
    session.close()
    return result is not None

def process_resume_in_background(file_path, filename, token, client_ip):
    try:
        if filename.lower().endswith('.pdf'):
            resume_text = extract_text_from_pdf(file_path)
        else:
            resume_text = extract_text_from_docx(file_path, advanced_mode=False)

        parsed_data = parse_resume(resume_text, filename)
        parsed_data['Date'] = datetime.now().strftime("%d/%m/%Y")
        parsed_data['original_filename'] = filename
        parsed_data['ip_address'] = client_ip

        gc = get_google_sheets_client()
        with open(file_path, 'rb') as f:
            file_content = f.read()
        drive_link = upload_to_google_drive(filename, file_content, gc)
        parsed_data['File Name'] = drive_link if drive_link else filename

        with sheet_lock:
            write_to_google_sheet(parsed_data, SPREADSHEET_ID)

        session = Session()
        new_resume = Resume(ip_address=client_ip, filename=filename, token=token)
        session.add(new_resume)
        session.commit()
        session.close()
    except Exception as e:
        print(f"Error processing resume in background: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.route('/career')
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
            shutil.copy(file_path, temp_file_path)
            file_references[filename] = filename

            for attempt in range(max_retries):
                try:
                    if filename.lower().endswith('.pdf'):
                        resume_text = extract_text_from_pdf(file_path)
                    else:
                        resume_text = extract_text_from_docx(file_path, advanced_mode=False)

                    estimated_tokens = estimate_tokens(resume_text)
                    if estimated_tokens > max_tokens:
                        resume_text = truncate_text(resume_text, max_tokens)

                    parsed_data = parse_resume(resume_text, filename)
                    if 'error' in parsed_data:
                        parsed_data['original_filename'] = filename
                    else:
                        parsed_data['Date'] = datetime.now().strftime("%d/%m/%Y")
                        parsed_data['original_filename'] = filename
                    parsed_resumes.append(parsed_data)
                    break
                except Exception as e:
                    if "rate_limit_exceeded" in str(e) and attempt < max_retries - 1:
                        print(f"Rate limit exceeded for {filename}, retrying in {retry_delay} seconds")
                        time.sleep(retry_delay)
                    else:
                        print(f"Error processing {filename}: {e}")
                        parsed_resumes.append({'original_filename': filename, 'error': str(e)})
                        break
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)
        else:
            parsed_resumes.append({'original_filename': file.filename, 'error': 'Unsupported file type'})

    return jsonify({'resumes': parsed_resumes, 'file_references': file_references})

@app.route('/save', methods=['POST'])
def save_to_sheet():
    data = request.json
    resumes = data.get('resumes', [])
    file_references = data.get('file_references', {})
    if not resumes:
        return jsonify({'error': 'No resumes to save'}), 400

    gc = get_google_sheets_client()
    success_count = 0

    for resume in resumes:
        try:
            if 'error' not in resume:
                filename = resume.get('original_filename', '')
                if not filename:
                    continue

                if filename in file_references:
                    temp_file_path = os.path.join(TEMP_STORAGE_FOLDER, filename)
                    if os.path.exists(temp_file_path):
                        with open(temp_file_path, 'rb') as f:
                            file_content = f.read()
                        drive_link = upload_to_google_drive(filename, file_content, gc)
                        resume['File Name'] = drive_link if drive_link else filename
                        os.remove(temp_file_path)
                    else:
                        resume['File Name'] = filename
                else:
                    resume['File Name'] = filename

                resume.pop('original_filename', None)
                write_to_google_sheet(resume, SPREADSHEET_ID)
                success_count += 1
        except Exception as e:
            print(f"Error saving {resume.get('original_filename', 'unknown')}: {e}")

    for filename in file_references:
        temp_file_path = os.path.join(TEMP_STORAGE_FOLDER, filename)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return jsonify({'message': f'Successfully saved {success_count} out of {len(resumes)} resumes'})

@app.route('/generate_link', methods=['POST'])
def generate_link():
    token = generate_encrypted_token()
    link = f"http://jobs.logbinary.com/apply/{token}"
    return jsonify({
        'link': link,
        'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
    })

@app.route('/apply/<token>', methods=['GET', 'POST'])
def upload_resume(token):
    if not validate_token(token):
        return render_template('invalid_link.html'), 403

    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()

    if has_ip_submitted(token, client_ip):
        return render_template('already_submitted.html'), 403

    if request.method == 'GET':
        return render_template('upload.html', token=token)

    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['resume']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    thread = threading.Thread(target=process_resume_in_background, args=(file_path, filename, token, client_ip))
    thread.start()

    time.sleep(2)
    return render_template('success.html')

if __name__ == '__main__':
    app.run(debug=True)