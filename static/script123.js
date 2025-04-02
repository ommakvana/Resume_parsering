
document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chatMessages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    const uploadContainer = document.getElementById('uploadContainer');
    const resumeUploadForm = document.getElementById('resumeUploadForm');

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', function(e) { if (e.key === 'Enter') sendMessage(); });
    resumeUploadForm.addEventListener('submit', function(e) { e.preventDefault(); uploadResume(); });

    function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;
        addMessage('user', message);
        userInput.value = '';
        fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            addMessage('bot', data.message);
            uploadContainer.style.display = data.enable_file_upload ? 'block' : 'none';
        })
        .catch(error => {
            console.error('Error:', error);
            addMessage('bot', 'Sorry, there was an error processing your request.');
        });
    }

    function addMessage(sender, message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        messageDiv.innerHTML = message;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function uploadResume() {
        const fileInput = document.getElementById('resumeFile');
        const file = fileInput.files[0];
        if (!file) {
            addMessage('bot', 'Please select a file to upload.');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        fetch('/api/upload-resume', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            addMessage('bot', data.message);
            uploadContainer.style.display = 'none';
            fileInput.value = '';
        })
        .catch(error => {
            console.error('Error:', error);
            addMessage('bot', 'Sorry, there was an error uploading your resume.');
        });
    }
});
    