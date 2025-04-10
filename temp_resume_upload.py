from flask import Flask, render_template, request, jsonify, url_for
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid
from data_ingestion.file_processor import process_single_resume, extract_text_from_pdf, extract_text_from_docx, parse_resume
from data_ingestion.config import SAVE_DIR, SPREADSHEET_ID
from Google_work.google_sheet import write_to_google_sheet, get_google_sheets_client
from Google_work.google_drive import upload_to_google_drive

app = Flask(__name__)

UPLOAD_FOLDER = 'temp_uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'rtf', 'txt', 'png', 'jpg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# Store for temporary links: {token: {'expiration': timestamp, 'submitted_ips': set}}
temp_links = {}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_temp_token():
    token = str(uuid.uuid4())
    expiration = datetime.now() + timedelta(hours=1)
    temp_links[token] = {
        'expiration': expiration,
        'submitted_ips': set()  # Track IPs that have submitted
    }
    return token

def is_link_valid(token, client_ip):
    if token not in temp_links:
        print(f"Token {token} not found")
        return False
    
    link_data = temp_links[token]
    current_time = datetime.now()
    
    # Check if link is expired
    if current_time > link_data['expiration']:
        print(f"Token {token} expired: {link_data['expiration']} < {current_time}")
        return False
    
    # Check if this IP has already submitted
    if client_ip in link_data['submitted_ips']:
        print(f"IP {client_ip} already submitted for token {token}")
        return False
    
    print(f"Token {token} valid for IP {client_ip}")
    return True

@app.route('/')
def index():
    return render_template('generate_link.html')

@app.route('/generate_link', methods=['POST'])
def generate_link():
    token = generate_temp_token()
    link = url_for('upload_resume', token=token, _external=True)
    return jsonify({
        'link': link,
        'expires_at': temp_links[token]['expiration'].isoformat()
    })

@app.route('/submit/<token>', methods=['GET', 'POST'])
def upload_resume(token):
    client_ip = request.remote_addr
    print(f"Request from IP: {client_ip} for token: {token}")
    
    if not is_link_valid(token, client_ip):
        return render_template('expired.html'), 403

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

    try:
        # Process the resume
        if filename.lower().endswith('.pdf'):
            resume_text = extract_text_from_pdf(file_path)
        else:
            resume_text = extract_text_from_docx(file_path, advanced_mode=False)

        parsed_data = parse_resume(resume_text, filename)
        parsed_data['Date'] = datetime.now().strftime("%d/%m/%Y")
        parsed_data['original_filename'] = filename
        parsed_data['ip_address'] = client_ip

        # Upload to Google Drive
        gc = get_google_sheets_client()
        with open(file_path, 'rb') as f:
            file_content = f.read()
        drive_link = upload_to_google_drive(filename, file_content, gc)
        if drive_link:
            parsed_data['File Name'] = drive_link
        else:
            parsed_data['File Name'] = filename

        # Save to Google Sheet
        write_to_google_sheet(parsed_data, SPREADSHEET_ID)

        # Mark this IP as having submitted for this token
        temp_links[token]['submitted_ips'].add(client_ip)
        print(f"IP {client_ip} marked as submitted   for token {token}")

        # Clean up
        os.remove(file_path)

        return render_template('success.html')

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7700, debug=True)