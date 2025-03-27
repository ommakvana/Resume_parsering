from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    print("Home route accessed")  # Debug
    return "Hello, World!"  # Temporary, bypasses success.html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7700, debug=True)