import os 
from typing import Dict, List, Any, Tuple,Optional,Type
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate , MessagesPlaceholder
from langchain.agents import create_structured_chat_agent
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.chains import LLMChain
from pydantic import BaseModel ,Field
from langchain.tools import BaseTool
from langchain.agents import AgentExecutor , create_react_agent
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import SystemMessage, HumanMessage, AIMessage

COMPANY_CONFIG = {
    "company_name": "LogBinary",
    "services": [
        {
            "id": "service1",
            "name": "Python Development",
            "description": "Custom Python solutions for web applications, APIs, and automation.",
            "details": "With Python we are bulding highly scalable server side applications. Using Django we can build any web based applications, APIs etc."
        },
        {
            "id": "service2",
            "name": "ML / AI",
            "description": "AI-driven solutions leveraging Machine Learning and Deep Learning.",
            "details": "Using Machine learning and Deep learning algorithms we build artificial intelligence products for various dynamic business needs."
        },
        {
            "id": "service3",
            "name": "Application Development",
            "description": "End-to-end mobile and web application development for businesses.",
            "details": "We Develope Mobile applications in android and flutter for various businesses. Design, Development, API Integrations, etc."
        },
    ],
    "careers": [
        {
            "id": "job1",
            "title": "Frontend Developer",
            "department": "Engineering",
            "type": "Full-time",
            "location": "on-site",
            "description": "We're looking for an experienced Frontend Developer to join our team. Proficiency in React, Vue, or Angular required."
        },
        {
            "id": "job2",
            "title": "UX/UI Designer",
            "department": "Design",
            "type": "Full-time",
            "location": "Hybrid",
            "description": "Seeking a creative UX/UI Designer to craft beautiful, intuitive interfaces for our clients' projects."
        },
    ],
    "contact_info": {
        "email":f"info@logbinary.com",
        "phone":"+91-931 678 9418",
        "hours": "Monday to Friday, 10:00 AM - 7:00 PM IST"
}
}

# Pydantic models for structured data
class ServiceInquiry(BaseModel):
    name: str = Field(description="Customer's full name")
    email: str = Field(description="Customer's email address")
    service_id: str = Field(description="ID of the service the customer is interested in")
    project_details: str = Field(description="Description of the customer's project or needs")

class JobApplication(BaseModel):
    name: str = Field(description="Applicant's full name")
    email: str = Field(description="Applicant's email address")
    job_id: str = Field(description="ID of the job the applicant is interested in")
    resume_link: str = Field(description="Link to the applicant's resume or portfolio")
    cover_letter: Optional[str] = Field(description="Optional cover letter or additional information")

#custom tools for the agent
class GetServicesListTool(BaseTool):
    name: str = "get_services_list"
    description:  str = "Get the list of services offered by the company."

    def _run(self,query : str= None)-> str:
        services = COMPANY_CONFIG["services"]
        response = f"At {COMPANY_CONFIG['company_name']}, we offer the following services:\n\n"

        for service in services:
            response += f"🔹 {service['name']}: {service['description']}\n"

        return response

class GetServiceDetailsTool(BaseTool)   :
    name:str  = "get_service_details"
    description:str = "Get detailed information about a specific service"
    
    def _run(self, service_id: str) -> str:
        services = COMPANY_CONFIG["services"]
        service = next((s for s in services if s["id"] == service_id), None)
        
        if not service:
            return f"Sorry, I couldn't find information about the service with ID {service_id}."
        
        return f"{service['name']}: {service['description']}\n\n{service['details']}"
    
class GetCareersListTool(BaseTool):
    name:str = "get_careers_list"  # Changed from "get_service_details"
    description:str = "Get the list of available careers at the company."
    
    def _run(self, query: str = None) -> str:
        jobs = COMPANY_CONFIG["careers"]
        response = f"Currently, we have the following career opportunities at {COMPANY_CONFIG['company_name']}:\n\n"
        
        for job in jobs:
            response += f"• {job['title']} ({job['department']}, {job['type']})\n"
        
        return response 
    
class GetJobsListTool(BaseTool):
    name:str = "get_jobs_list"
    description:str = "Get the list of current job openings at the company."

    def _run(self,query : str = None) -> str:
        jobs = COMPANY_CONFIG['careers']
        response = f"Currently, we have the following open positions at {COMPANY_CONFIG['company_name']}:\n\n"

        for job in jobs:
            response += f"• {job['title']} ({job['department']}, {job['type']}, {job['location']})\n"
        
        return response
    
class GetJobDetailsTool(BaseTool):
    name:str = "get_job_details"
    description :str= "Get detailed information about a specific job opening."

    def _run(self,job_id :str =None) -> str:
        jobs = COMPANY_CONFIG["careers"]
        job = next((j for j in jobs if j["id"] == job_id), None)

        if not job :
            return f"Sorry, I couldn't find information about the job with ID {job_id}."
        
        return f"{job['title']} ({job['type']}, {job['location']})\n\n{job['description']}"

class SubmitServiceInquiryTool(BaseTool):
    name :str= "submit_service_inquiry"
    description:str = "Submit a service inquiry from a potential customer."
    args_schema: Type[BaseModel] = ServiceInquiry

    def _run(self, name: str, email: str, service_id: str, project_details: str) -> str:

        services = COMPANY_CONFIG["services"]
        service = next((s for s in services if s["id"] == service_id), None)

        if not service:
            return f"Sorry, I couldn't find the service with ID {service_id}."
        
        print(f"Service inquiry submitted: {name}, {email}, {service['name']}, {project_details}")

        return f"Thank you, {name}! Your inquiry about {service['name']} has been submitted. Our team will contact you at {email} within 1-2 business days to discuss your project needs."

class SubmitJobApplicationTool(BaseTool):
    name: str = "submit_job_application"
    description: str = "Submit a job application from a potential candidate"
    args_schema: Type[BaseModel] = JobApplication
    
    def _run(self, name: str, email: str, job_id: str, resume_link: str, cover_letter: Optional[str] = None) -> str:
        # In a real implementation, this would connect to a database or API
        # Here we'll just print the information
        jobs = COMPANY_CONFIG["careers"]
        job = next((j for j in jobs if j["id"] == job_id), None)
        
        if not job:
            return f"Sorry, I couldn't find the job with ID {job_id}."
        
        print(f"Job application submitted: {name}, {email}, {job['title']}, {resume_link}")
        
        return f"Thank you, {name}! Your application for the {job['title']} position has been submitted. Our HR team will review your application and reach out to you at {email} if there's a potential match."

class GetContactInfoTool(BaseTool):
    name :str = "get_contact_info"
    description :str = "Get the contact information for the company."

    def _run(self, query: str = None) -> str:
        contact = COMPANY_CONFIG["contact_info"]

        return f"You can contact {COMPANY_CONFIG['company_name']} through the following channels:\n\n" \
               f"- Email: {contact['email']}\n" \
               f"- Phone: {contact['phone']}\n" \
               f"- Office Hours: {contact['hours']}"
    
from langchain.agents.agent_types import AgentType
from langchain.agents import initialize_agent
from langchain.tools.render import format_tool_to_openai_function

def create_company_agent():
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        max_tokens=None,
        api_key=OPENAI_API_KEY
    )
    
    tools = [
        GetServicesListTool(),
        GetServiceDetailsTool(),
        GetJobsListTool(),
        GetJobDetailsTool(),
        SubmitServiceInquiryTool(),
        SubmitJobApplicationTool(),
        GetContactInfoTool(),
    ]

    # Convert tools to OpenAI function format
    llm_with_tools = llm.bind(
        functions=[format_tool_to_openai_function(t) for t in tools]
    )

    # Create a custom system message
    system_message = f"""
    You are an AI assistant for {COMPANY_CONFIG['company_name']}'s website.
    Your job is to help visitors learn about our services, explore job opportunities, and submit inquiries or applications.
    
    Be professional, friendly, and helpful. Always maintain a conversational tone.
    
    Start by greeting the visitor and asking how you can help them. If they're interested in:
    
    - Services: Use the get_services_list tool and offer to provide more details about specific services.
    - Jobs: Use the get_jobs_list tool and offer to provide more details about specific positions.
    - Contact: Use the get_contact_info tool to provide the company's contact information.
    
    If a visitor wants to submit a service inquiry, collect their name, email, service of interest, and project details.
    If a visitor wants to apply for a job, collect their name, email, position of interest, and resume link.
    
    Always follow up after form submissions to confirm the information has been received and set appropriate expectations.
    """

    # For OpenAI function calling, we'll use a different approach
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    
    # Import the correct utils
    from langchain_core.utils.function_calling import convert_to_openai_function
    
    # Create a chain that uses the OpenAI functions format
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Use the openai functions agent output parser
    agent = (
        {
            "input": lambda x: x["input"],
            "chat_history": lambda x: x.get("chat_history", []),
            "agent_scratchpad": lambda x: format_to_openai_function_messages(x.get("intermediate_steps", [])),
        }
        | prompt
        | llm_with_tools
        | OpenAIFunctionsAgentOutputParser()
    )
    
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        max_iterations=3,
        early_stopping_method="generate",
        handle_parsing_errors=True,
    )

    return agent_executor

class CompanyAIChatbot:
    def __init__(self):
        self.agent = create_company_agent()
        self.conversation_history =[]

    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the chatbot's response"""
        try:
            response = await self.agent.ainvoke({"input": user_message})
            return response["output"]
        
        except Exception as e:
            print(f"Error processing message: {e}")
            return "I'm having trouble processing your request. Please try again or contact our support team directly."
        
from fastapi import FastAPI , websockets, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import uvicorn

app = FastAPI()

@app.get("/")
async def get():
    with open("index_234.html") as f:
        html_content= f.read()
    return HTMLResponse(html_content)

@app.websocket("/ws")
async def websocket_endpoint(websocket: websockets.WebSocket):
    await websocket.accept()
    
    try:
        # Create the chatbot only once
        chatbot = CompanyAIChatbot()
        
        # Send an initial greeting
        # await websocket.send_text("Hello! Welcome to our website. How can I assist you today?")
        
        while True:
            # Make sure to await the receive_text
            data = await websocket.receive_text()
            # Process the message
            response = await chatbot.process_message(data)
            # Send the response
            await websocket.send_text(response)
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error in websocket: {e}")
        try:
            await websocket.send_text("I'm having trouble processing your request. Please try again or contact our support team directly.")
        except:
            print("Failed to send error message")

# Helper function to create a simple HTML file for testing
def create_test_html():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Company AI Chatbot</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; display: flex; justify-content: center; }
            .chat-container { width: 100%; max-width: 600px; margin: 20px; }
            .chat-box { height: 400px; border: 1px solid #ccc; overflow-y: auto; padding: 10px; margin-bottom: 10px; }
            .user-message { background-color: #e6f7ff; padding: 8px; border-radius: 15px; margin: 5px 0; max-width: 80%; align-self: flex-end; margin-left: auto; }
            .bot-message { background-color: #f0f0f0; padding: 8px; border-radius: 15px; margin: 5px 0; max-width: 80%; }
            .input-area { display: flex; }
            #message-input { flex-grow: 1; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
            #send-button { padding: 10px 15px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; margin-left: 10px; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <h1>Company AI Chatbot</h1>
            <div id="chat-box" class="chat-box"></div>
            <div class="input-area">
                <input type="text" id="message-input" placeholder="Type your message here...">
                <button id="send-button">Send</button>
            </div>
        </div>
        
        <script>
            const chatBox = document.getElementById('chat-box');
            const messageInput = document.getElementById('message-input');
            const sendButton = document.getElementById('send-button');
            
            // Connect to WebSocket
            const socket = new WebSocket('ws://' + window.location.host + '/ws');
            
            socket.onopen = function(e) {
                console.log('WebSocket connection established');
                addBotMessage('Hello! Welcome to our website. How can I assist you today?');
            };
            
            socket.onmessage = function(event) {
                addBotMessage(event.data);
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
            
            // Send message when button is clicked
            sendButton.addEventListener('click', sendMessage);
            
            // Send message when Enter key is pressed
            messageInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            function sendMessage() {
                const message = messageInput.value.trim();
                if (message) {
                    // Add user message to chat
                    addUserMessage(message);
                    
                    // Send message to server
                    socket.send(message);
                    
                    // Clear input field
                    messageInput.value = '';
                }
            }
            
            function addUserMessage(message) {
                const messageElement = document.createElement('div');
                messageElement.classList.add('user-message');
                messageElement.textContent = message;
                chatBox.appendChild(messageElement);
                chatBox.scrollTop = chatBox.scrollHeight;
            }
            
            function addBotMessage(message) {
                const messageElement = document.createElement('div');
                messageElement.classList.add('bot-message');
                messageElement.textContent = message;
                chatBox.appendChild(messageElement);
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        </script>
    </body>
    </html>
    """
    
    with open("index_234.html", "w") as file:
        file.write(html)

create_test_html()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0",port=6440)