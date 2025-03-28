from flask import Flask, render_template, request, jsonify, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import threading
from itsdangerous import URLSafeTimedSerializer, BadSignature  # For encrypted tokens
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# Import file processing and Google functions
from data_ingestion.file_processor import process_single_resume, extract_text_from_pdf, extract_text_from_docx, parse_resume
from data_ingestion.config import SAVE_DIR, SPREADSHEET_ID
from Google_work.google_sheet import write_to_google_sheet, get_google_sheets_client
from Google_work.google_drive import upload_to_google_drive

app = Flask(__name__)

# Secret key for encryption (replace with a secure key in production)
app.config['SECRET_KEY'] = 'your-secure-secret-key-here'  # Change this to a strong secret

UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'rtf', 'txt', 'png', 'jpg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# Set up SQLite database
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

# URL-safe serializer for encrypting tokens
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_encrypted_token():
    # Generate a simple token payload (e.g., current timestamp or random data)
    data = {'created_at': datetime.now().isoformat()}
    # Encrypt the data into a token
    return serializer.dumps(data)

def validate_token(token):
    try:
        # Decrypt the token (no expiration enforced unless specified)
        serializer.loads(token)  # We just check if it’s valid
        return True
    except BadSignature:
        return False

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

ACCESS_KEY = '7876'  # Replace with a strong, unique key

# Optional: Hash the access key for added security
HASHED_ACCESS_KEY = generate_password_hash(ACCESS_KEY)

@app.route('/career', methods=['GET', 'POST'])
def career_access():
    # If user is already authenticated, redirect to the main career page
    if session.get('career_authenticated', False):
        return render_template('generate_link.html')  # Your existing career page template

    # Handle key submission
    if request.method == 'POST':
        submitted_key = request.form.get('access_key', '')
        
        # Check if the submitted key is correct
        if check_password_hash(HASHED_ACCESS_KEY, submitted_key):
            # Set session to authenticated
            session['career_authenticated'] = True
            
            # Redirect to the career page
            return render_template('generate_link.html')
        else:
            # Incorrect key
            return render_template('key_access.html', error='Invalid access key')

    # Show key input page for GET requests
    return render_template('key_access.html')

# Create a logout route to remove authentication
@app.route('/career/logout')
def career_logout():
    session.pop('career_authenticated', None)
    return redirect('/career')

# Modify existing routes to check for authentication
def career_authentication_required(f):
    def wrapper(*args, **kwargs):
        if not session.get('career_authenticated', False):
            return redirect('/career')
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Example of how to protect other career-related routes
@app.route('/generate_link', methods=['POST'])
@career_authentication_required
def generate_link():
    # Your existing generate_link logic
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

    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()
        
    print(f"Request from IP: {client_ip} for token: {token}")

    if has_ip_submitted(token, client_ip):
        return render_template('already_submitted.html'), 403

    if request.method == 'GET':
        return render_template('upload.html', token=token)  # Same page for all valid tokens

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
    pass