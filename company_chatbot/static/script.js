// DOM Elements
const chatWidget = document.getElementById('chat-widget');
const chatBox = document.getElementById('chat-box');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const chatToggleButton = document.getElementById('chat-toggle-button');
const minimizeButton = document.getElementById('minimize-button');
const closeButton = document.getElementById('close-button');

// WebSocket State
let socket = new WebSocket('ws://' + window.location.host + '/ws');
window.socket = socket; // Make socket globally accessible
let isClosed = false;

// Chat State
let hasShownSuggestions = false;
let lastBotMessage = null;
let chatActive = false;
let chatSessionTimeout = null;
const SESSION_TIMEOUT = 15 * 60 * 1000; // 15 minutes in milliseconds

// Initialize Chat Widget
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Loaded');
    console.log('chatToggleButton:', chatToggleButton);
    console.log('chatWidget:', chatWidget);
    addGlobalStyles();
    chatToggleButton.classList.remove('hidden');

    chatToggleButton.addEventListener('click', toggleChat);
    minimizeButton.addEventListener('click', minimizeChat);
    closeButton.addEventListener('click', showClearPopupInsideChat); // Updated to trigger new popup
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') sendMessage();
    });

    // WebSocket Event Handlers
    socket.onopen = function(e) {
        console.log('WebSocket connection established');
        isClosed = false;
        if (chatBox.childElementCount === 0 && chatWidget.classList.contains('visible')) {
        }
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
        isClosed = true;
    };

    socket.onerror = function(error) {
        console.error(`WebSocket error: ${error.message}`);
    };
});

// Chat Functions
function toggleChat() {
    if (chatWidget.classList.contains('visible')) {
        minimizeChat();
    } else {
        showChat();
    }
}

function showChat() {
    chatWidget.classList.add('visible');
    chatWidget.classList.remove('minimized');
    chatActive = true;
    
    // Reset session timeout
    resetSessionTimeout();
    
    // Re-establish WebSocket if closed
    if (isClosed || socket.readyState === WebSocket.CLOSED) {
        socket.close(); // Close any existing closed connection
        socket = new WebSocket('ws://' + window.location.host + '/ws');
        window.socket = socket;
        
        // Reattach event handlers
        socket.onopen = function(e) {
            console.log('WebSocket connection re-established');
            isClosed = false;
            if (chatBox.childElementCount === 0) {
            }
        };
        socket.onmessage = function(event) {
            console.log("Received message:", event.data);
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) typingIndicator.remove();
            if (event.data !== "Typing..." && event.data !== lastBotMessage) {
                lastBotMessage = event.data;
                addBotMessage(event.data);
                messageInput.focus();
            }
        };
        socket.onclose = function(event) {
            if (event.wasClean) {
                console.log(`Connection closed cleanly, code=${event.code} reason=${event.reason}`);
            } else {
                console.error('Connection died');
            }
            isClosed = true;
        };
        socket.onerror = function(error) {
            console.error(`WebSocket error: ${error.message}`);
        };
    } else if (chatBox.childElementCount === 0 && socket.readyState === WebSocket.OPEN) {
    }
}

function minimizeChat() {
    chatWidget.classList.remove('visible');
    chatWidget.classList.add('minimized');
}

function closeChat() {
    chatWidget.classList.remove('visible');
    chatWidget.classList.add('minimized');
    
    // Clear session timeout
    if (chatSessionTimeout) {
        clearTimeout(chatSessionTimeout);
    }
    
    // Reset chat immediately
    chatBox.innerHTML = '';
    hasShownSuggestions = false;
    lastBotMessage = null;
    messageInput.value = ''; // Clear input field
    chatActive = false;
    
    // Close WebSocket
    if (socket.readyState === WebSocket.OPEN) {
        socket.close();
        console.log('WebSocket connection closed to reset session');
    }
}

function resetSessionTimeout() {
    if (chatSessionTimeout) {
        clearTimeout(chatSessionTimeout);
    }
    chatSessionTimeout = setTimeout(function() {
        if (chatActive) {
            // Close WebSocket on timeout
            if (socket.readyState === WebSocket.OPEN) {
                socket.close();
                console.log('WebSocket closed due to 15-minute timeout');
            }
            // Reset chat state
            chatBox.innerHTML = '';
            hasShownSuggestions = false;
            lastBotMessage = null;
            messageInput.value = '';
            chatActive = false;
            isClosed = true;
            // Minimize to toggle button
            minimizeChat();
        }
    }, SESSION_TIMEOUT);
}

function sendMessage() {
    const message = messageInput.value.trim();
    if (message) {
        // Re-establish WebSocket if closed (e.g., due to timeout)
        if (isClosed || socket.readyState === WebSocket.CLOSED) {
            socket.close(); // Close any existing closed connection
            socket = new WebSocket('ws://' + window.location.host + '/ws');
            window.socket = socket;
            
            socket.onopen = function(e) {
                console.log('WebSocket connection re-established');
                isClosed = false;
                socket.send(message); // Resend the message after connection
                showTypingIndicator();
            };
            socket.onmessage = function(event) {
                console.log("Received message:", event.data);
                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator) typingIndicator.remove();
                if (event.data !== "Typing..." && event.data !== lastBotMessage) {
                    lastBotMessage = event.data;
                    addBotMessage(event.data);
                    messageInput.focus();
                }
            };
            socket.onclose = function(event) {
                if (event.wasClean) {
                    console.log(`Connection closed cleanly, code=${event.code} reason=${event.reason}`);
                } else {
                    console.error('Connection died');
                }
                isClosed = true;
            };
            socket.onerror = function(error) {
                console.error(`WebSocket error: ${error.message}`);
            };
        } else if (socket.readyState === WebSocket.OPEN) {
            addUserMessage(message);
            socket.send(message);
            messageInput.value = '';
            showTypingIndicator();
        }
        resetSessionTimeout();
        const suggestionContainer = document.getElementById('suggestion-container');
        if (suggestionContainer) {
            suggestionContainer.remove();
        }
    }
}

function addUserMessage(message) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'user-message');
    messageElement.innerHTML = `<div class="message-content"><div class="message-bubble">${message}</div></div>`;
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
                <div class="message-bubble">${message}</div>
        `;
        if (!hasShownSuggestions) {
            messageContent += `
                <div class="suggestion-container" id="suggestion-container">
                    <div class="suggestion-buttons">
                        <button class="suggestion-button" data-question="Tell me about your services">Tell me about your services</button>
                        <button class="suggestion-button" data-question="What job openings are available?">What job openings are available?</button>
                        <button class="suggestion-button" data-question="How can I contact you?">How can I contact you?</button>
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
        const inquiryForm = messageElement.querySelector('#inquiryForm');
        if (inquiryForm) {
            inquiryForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                if (!socket || socket.readyState !== WebSocket.OPEN) {
                    console.error('WebSocket is not open');
                    return;
                }
                const formData = new FormData(this);
                const data = Object.fromEntries(formData);
                await socket.send(JSON.stringify({ 
                    action: 'submit_inquiry', 
                    data: { 
                        name: data.name,  
                        email: data.email,
                        phone: data.phone,
                        subject: data.subject,
                        message: data.message,
                        service_id: data.service_id || ''  
                    } 
                }));
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
                const formData = new FormData();
                const resumeFile = this.querySelector('#resume').files[0];
                if (!resumeFile) {
                    alert('Please upload your resume.');
                    return false;
                }
                try {
                    formData.append('file', resumeFile);
                    const uploadResponse = await fetch('/upload-resume', { method: 'POST', body: formData });
                    if (!uploadResponse.ok) throw new Error(`Resume upload failed: ${uploadResponse.statusText}`);
                    const uploadResult = await uploadResponse.json();
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
                    socket.send(JSON.stringify({ action: 'submit_job_application', data: applicationData }));
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
        .message-bubble { padding: 12px 15px; border-radius: 8px; font-size: 14px; line-height: 1.5; color: #232f3e; width: auto; display: inline-block; max-width: 100%; border: 1px solid #e9ebed; background-color: #f8f9fa; }
        .bot-message .message-bubble { border: 1px solid #e9ebed; background-color: #f8f9fa; }
        .welcome-message { font-size: 15px; line-height: 1.5; }
        .message-bubble ul, .message-bubble ol { padding-left: 20px; margin: 8px 0; }
        .message-bubble li { margin-bottom: 6px; }
        .service-card { border: 1px solid #e9ebed; border-radius: 8px; padding: 12px; margin: 8px 0; background-color: #f8f9fa; }
        .service-title { font-weight: 600; color: #0972d3; margin-bottom: 6px; }
        .service-description { font-size: 13px; color: #232f3e; }
        .job-listing { border-left: 3px solid #0972d3; padding-left: 12px; margin: 12px 0; }
        .job-title { font-weight: 600; color: #232f3e; }
        .inquiry-form { border: 1px solid #e9ebed; border-radius: 8px; padding: 16px; background-color: #f8f9fa; margin: 12px 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        .inquiry-form p { margin-bottom: 16px; color: #232f3e; font-size: 14px; line-height: 1.5; }
        .form-group { margin-bottom: 12px; }
        .form-group label { font-weight: 600; color: #232f3e; display: block; margin-bottom: 4px; font-size: 14px; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 8px; border: 1px solid #d9d9d9; border-radius: 4px; box-sizing: border-box; font-family: inherit; font-size: 14px; }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { outline: none; border-color: #0972d3; box-shadow: 0 0 0 2px rgba(9, 114, 211, 0.2); }
        .form-group textarea { min-height: 80px; resize: vertical; }
        .form-group input[type="submit"] { background-color: #0972d3; color: white; border: none; cursor: pointer; padding: 10px 20px; font-weight: 600; transition: background-color 0.2s; }
        .form-group input[type="submit"]:hover { background-color: #075aad; }
        .form-group input[type="file"] { padding: 6px; border: 1px dashed #d9d9d9; background-color: #fff; }
        .inquiry-confirmation, .application-confirmation, .error-message { padding: 12px; border-radius: 6px; margin: 8px 0; font-size: 14px; line-height: 1.5; }
        .inquiry-confirmation, .application-confirmation { background-color: #f0f7ff; border-left: 3px solid #0972d3; color: #232f3e; }
        .error-message { background-color: #fff0f0; border-left: 3px solid #d13212; color: #d13212; }
        #chat-box {
            padding: 10px;
            position: relative; /* Ensure positioning context for popup */
        }
        /* Add blur overlay styles */
        .blur-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(85, 59, 59, 0.1);
            backdrop-filter: blur(5px);
            -webkit-backdrop-filter: blur(5px);
            z-index: 5;
        }
        
        /* Update the chat popup styles */
        .chat-popup {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            text-align: center;
            z-index: 10; /* Above the blur overlay */
            max-width: 90%;
            width: 300px;
        }
        .chat-popup-header {
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 10px;
            color: #232f3e;
        }
        .chat-popup-close {
            position: absolute;
            top: 10px;
            right: 10px;
            cursor: pointer;
            font-size: 18px;
            color: #666;
        }
        .chat-popup-buttons {
            margin-top: 15px;
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }
        .chat-popup-cancel, .chat-popup-clear {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
        }
        .chat-popup-cancel {
            background-color: #f0f0f0;
            color: #232f3e;
        }
        .chat-popup-clear {
            background-color: #7558F7;
            color: white;
        }
        .chat-popup-cancel:hover {
            background-color: #e0e0e0;
        }
        .chat-popup-clear:hover {
            background-color: #7558F7;
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

function showClearPopupInsideChat() {
    // Remove any existing popup
    let existingPopup = chatBox.querySelector('.chat-popup');
    if (existingPopup) existingPopup.remove();
    
    // Create blur overlay
    const blurOverlay = document.createElement('div');
    blurOverlay.classList.add('blur-overlay');
    chatBox.appendChild(blurOverlay);

    // Create popup
    const popup = document.createElement('div');
    popup.classList.add('chat-popup');
    popup.innerHTML = `
        <div class="chat-popup-header">Clear conversation</div>
        <span class="chat-popup-close">×</span>
        <p>All messages in the chat will be cleared. Would you like to clear this conversation?</p>
        <div class="chat-popup-buttons">
            <button class="chat-popup-No">No</button>
            <button class="chat-popup-Yes">Yes</button>
        </div>
    `;
    chatBox.appendChild(popup);

    // Add event listeners
    const closePopup = popup.querySelector('.chat-popup-close');
    const cancelButton = popup.querySelector('.chat-popup-No');
    const clearButton = popup.querySelector('.chat-popup-Yes');

    closePopup.addEventListener('click', removePopup);
    cancelButton.addEventListener('click', removePopup);
    clearButton.addEventListener('click', function() {
        closeChat();
        removePopup();
    });

    function removePopup() {
        popup.remove();
        blurOverlay.remove();
    }
}