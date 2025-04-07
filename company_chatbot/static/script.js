const chatBox = document.getElementById('chat-box');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');

const socket = new WebSocket('ws://' + window.location.host + '/ws');
window.socket = socket; // Make socket globally accessible
let hasShownSuggestions = false;
let lastBotMessage = null;

socket.onopen = function(e) {
    console.log('WebSocket connection established');
};

socket.onmessage = function(event) {
    console.log("Received message:", event.data);
    
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) typingIndicator.remove(); // Clear typing indicator on new message
    
    if (event.data !== "Typing..." && event.data !== lastBotMessage) {
        lastBotMessage = event.data;
        addBotMessage(event.data);
        // Ensure input is focused after response
        messageInput.focus();
    }
};

socket.onclose = function(event) {
    if (event.wasClean) {
        console.log(`Connection closed cleanly, code=${event.code} reason=${event.reason}`);
    } else {
        console.error('Connection died');
    }
};

socket.onerror = function(error) {
    console.error(`WebSocket error: ${error.message}`);
};

sendButton.addEventListener('click', sendMessage);

messageInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

function sendMessage() {
    const message = messageInput.value.trim();
    if (message) {
        addUserMessage(message);
        socket.send(message);
        messageInput.value = '';
        showTypingIndicator();
        
        const suggestionContainer = document.getElementById('suggestion-container');
        if (suggestionContainer) {
            suggestionContainer.remove();
        }
    }
}

function addUserMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'user-message');
    
    messageElement.innerHTML = `
        <div class="message-content">
            <div class="message-bubble">${message}</div>
        </div>
    `;
    
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function addBotMessage(message) {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) typingIndicator.remove();
    
    if (message !== "Typing...") {
        lastBotMessage = message;

        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'bot-message');
        
        let messageContent = `
            <div class="avatar bot-avatar">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
            </div>
            <div class="message-content">
                <div class="message-bubble">
                    ${message}
                </div>
        `;
        
        if (!hasShownSuggestions) {
            messageContent += `
                <div class="suggestion-container" id="suggestion-container">
                    <div class="suggestion-buttons">
                        <button class="suggestion-button" data-question="I am interested in your services">I am interested in your services</button>
                        <button class="suggestion-button" data-question="I want to know about Job openings">I want to know about Job openings</button>
                        <button class="suggestion-button" data-question="I need Contact Information">I need Contact Information</button>
                    </div>
                </div>
            `;
        }
        
        messageContent += `</div>`;
        messageElement.innerHTML = messageContent;
        
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
        
        if (!hasShownSuggestions) {
            const suggestionButtons = messageElement.querySelectorAll('.suggestion-button');
            suggestionButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const question = this.getAttribute('data-question');
                    addUserMessage(question);
                    socket.send(question);
                    showTypingIndicator();
                    
                    const suggestionContainer = document.getElementById('suggestion-container');
                    if (suggestionContainer) {
                        suggestionContainer.remove();
                    }
                });
            });
            hasShownSuggestions = true;
        }

        // Handle inquiry form submission
        const inquiryForm = messageElement.querySelector('#inquiryForm');
        if (inquiryForm) {
            inquiryForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                console.log('Form submission triggered');
                if (!socket || socket.readyState !== WebSocket.OPEN) {
                    console.error('WebSocket is not open');
                    return;
                }
                const formData = new FormData(this);
                const data = Object.fromEntries(formData);
                const fullName = `${data.first_name} ${data.last_name}`; // Note: This assumes first_name and last_name fields, adjust if different
                await socket.send(JSON.stringify({ action: 'submit_inquiry', data: { ...data, name: fullName } }));
                // Replace the form with the thank you message
                const parentMessage = this.closest('.message');
                if (parentMessage && !parentMessage.querySelector('.message-bubble').innerHTML.includes('Thank you!')) {
                    parentMessage.querySelector('.message-bubble').innerHTML = 'Thank you! Your record has been submitted. Is there anything else we can help you with?';
                }
                return false;
            });
        }
        const jobApplicationForm = messageElement.querySelector('#jobApplicationForm');
        if (jobApplicationForm) {
            jobApplicationForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                console.log('Job application submission triggered');
                
                const formData = new FormData();
                const resumeFile = this.querySelector('#resume').files[0];
                
                if (!resumeFile) {
                    alert('Please upload your resume.');
                    return false;
                }
                
                try {
                    // 1. Upload the file
                    formData.append('file', resumeFile);
                    console.log('Uploading resume file:', resumeFile.name);
                    
                    const uploadResponse = await fetch('/upload-resume', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!uploadResponse.ok) {
                        throw new Error(`Resume upload failed: ${uploadResponse.statusText}`);
                    }
                    
                    const uploadResult = await uploadResponse.json();
                    console.log('Resume uploaded successfully:', uploadResult);
                    
                    // 2. Send application data via WebSocket
                    if (!socket || socket.readyState !== WebSocket.OPEN) {
                        console.error('WebSocket is not open');
                        alert('Connection error. Please try again.');
                        return false;
                    }
                    
                    const applicationData = {
                        name: this.querySelector('#name').value,
                        email: this.querySelector('#email').value,
                        phone: this.querySelector('#phone').value,
                        resume_file: uploadResult.filename
                    };
                    
                    console.log('Sending application data:', applicationData);
                    socket.send(JSON.stringify({ 
                        action: 'submit_job_application', 
                        data: applicationData 
                    }));
                    
                    // Replace the form with a thank you message
                    const parentMessage = this.closest('.message-bubble');
                    if (parentMessage) {
                        parentMessage.innerHTML = 'Thank you! Your job application has been submitted successfully. We will review your resume and get back to you soon.';
                    }
                    
                } catch (error) {
                    console.error('Error in job application submission:', error);
                    alert('There was an error submitting your application. Please try again.');
                    const parentMessage = this.closest('.message-bubble');
                    if (parentMessage) {
                        parentMessage.innerHTML = 'Error submitting application. Please try again.';
                    }
                }
                
                return false;
            });
        }
    }
}

function addGlobalStyles() {
    const styleElement = document.createElement('style');
    styleElement.textContent = `
        .message-bubble {
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.5;
            color: #232f3e;
            width: auto;
            display: inline-block;
            max-width: 100%;
            border: 1px solid #e9ebed; /* Ensure single border */
            background-color: #f8f9fa;
        }
        
        .bot-message .message-bubble {
            border: 1px solid #e9ebed; /* Override if needed */
            background-color: #f8f9fa;
        }
        
        .welcome-message {
            font-size: 15px;
            line-height: 1.5;
        }
        
        .message-bubble ul, 
        .message-bubble ol {
            padding-left: 20px;
            margin: 8px 0;
        }
        
        .message-bubble li {
            margin-bottom: 6px;
        }
        
        .service-card {
            border: 1px solid #e9ebed;
            border-radius: 8px;
            padding: 12px;
            margin: 8px 0;
            background-color: #f8f9fa;
        }
        
        .service-title {
            font-weight: 600;
            color: #0972d3;
            margin-bottom: 6px;
        }
        
        .service-description {
            font-size: 13px;
            color: #232f3e;
        }
        
        .job-listing {
            border-left: 3px solid #0972d3;
            padding-left: 12px;
            margin: 12px 0;
        }
        
        .job-title {
            font-weight: 600;
            color: #232f3e;
        }
        
        .inquiry-form {
            border: 1px solid #e9ebed;
            border-radius: 8px;
            padding: 16px;
            background-color: #f8f9fa;
            margin: 12px 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        
        .inquiry-form p {
            margin-bottom: 16px;
            color: #232f3e;
            font-size: 14px;
            line-height: 1.5;
        }
        
        .form-group {
            margin-bottom: 12px;
        }
        
        .form-group label {
            font-weight: 600;
            color: #232f3e;
            display: block;
            margin-bottom: 4px;
            font-size: 14px;
        }
        
        .form-group input, 
        .form-group select, 
        .form-group textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid #d9d9d9;
            border-radius: 4px;
            box-sizing: border-box;
            font-family: inherit;
            font-size: 14px;
        }
        
        .form-group input:focus, 
        .form-group select:focus, 
        .form-group textarea:focus {
            outline: none;
            border-color: #0972d3;
            box-shadow: 0 0 0 2px rgba(9, 114, 211, 0.2);
        }
        
        .form-group textarea {
            min-height: 80px;
            resize: vertical;
        }
        
        .form-group input[type="submit"] {
            background-color: #0972d3;
            color: white;
            border: none;
            cursor: pointer;
            padding: 10px 20px;
            font-weight: 600;
            transition: background-color 0.2s;
        }
        
        .form-group input[type="submit"]:hover {
            background-color: #075aad;
        }
        
        .form-group input[type="file"] {
            padding: 6px;
            border: 1px dashed #d9d9d9;
            background-color: #fff;
        }
        
        .inquiry-confirmation, 
        .application-confirmation,
        .error-message {
            padding: 12px;
            border-radius: 6px;
            margin: 8px 0;
            font-size: 14px;
            line-height: 1.5;
        }
        
        .inquiry-confirmation, 
        .application-confirmation {
            background-color: #f0f7ff;
            border-left: 3px solid #0972d3;
            color: #232f3e;
        }
        
        .error-message {
            background-color: #fff0f0;
            border-left: 3px solid #d13212;
            color: #d13212;
        }
    `;
    document.head.appendChild(styleElement);
}

function showTypingIndicator() {
    const typingElement = document.createElement('div');
    typingElement.classList.add('message', 'bot-message');
    typingElement.id = 'typing-indicator';
    
    typingElement.innerHTML = `
        <div class="avatar bot-avatar">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
        </div>
        <div class="message-content">
            <div class="message-bubble">Typing...</div>
        </div>
    `;
    
    chatBox.appendChild(typingElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}