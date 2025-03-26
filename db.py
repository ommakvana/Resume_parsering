from flask import Flask, render_template, request, jsonify, url_for
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import threading  # Import threading module
# Import file processing and Google functions
from data_ingestion.file_processor import process_single_resume, extract_text_from_pdf, extract_text_from_docx, parse_resume
from data_ingestion.config import SAVE_DIR, SPREADSHEET_ID
from Google_work.google_sheet import write_to_google_sheet, get_google_sheets_client
from Google_work.google_drive import upload_to_google_drive

app = Flask(__name__)

UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'rtf', 'txt', 'png', 'jpg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# Set up SQLite database
engine = create_engine('sqlite:////home/logbinary/Downloads/resumes.db', echo=True)
Base = declarative_base()

class Resume(Base):
    __tablename__ = 'resumes'
    id = Column(Integer, primary_key=True)
    ip_address = Column(String)
    filename = Column(String)
    token = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_temp_token():
    return str(uuid.uuid4())

def has_ip_submitted(token, ip_address):
    session = Session()
    result = session.query(Resume).filter_by(token=token, ip_address=ip_address).first()
    session.close()
    return result is not None

sheet_lock = threading.Lock()
# Background processing function
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

        # Serialize access to Google Sheets
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

@app.route('/')
def index():
    return render_template('generate_link.html')

@app.route('/generate_link', methods=['POST'])
def generate_link():
    token = generate_temp_token()
    link = f"https://jobs.logbinary.com/submit/{token}"
    return jsonify({
        'link': link,
        'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
    })

@app.route('/submit/<token>', methods=['GET', 'POST'])
def upload_resume(token):
    client_ip = request.remote_addr
    print(f"Request from IP: {client_ip} for token: {token}")

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

    return render_template('success.html')
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7700, debug=True)