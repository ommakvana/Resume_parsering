import os
import json
import logging
import traceback
import asyncio
from typing import Dict, List, Any, Tuple, Optional, Type, Union
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq  # Replace OpenAI with Gro

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("chatbot.log"), logging.StreamHandler()]
)
logger = logging.getLogger("company_chatbot")

# Load environment variables
load_dotenv()

# API keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Add to .env
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in environment variables")

COMPANY_CONFIG = {
    "company_name": "LogBinary",
    "services": [
        {
            "id": "service1",
            "name": "Python Development",
            "description": "Custom Python solutions for web applications, APIs, and automation.",
            "details": "With Python we are building highly scalable server side applications. Using Django we can build any web based applications, APIs etc."
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
            "details": "We Develop Mobile applications in Android and Flutter for various businesses. Design, Development, API Integrations, etc."
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
        "email": "info@logbinary.com",
        "phone": "+91-931 678 9418",
        "hours": "Monday to Friday, 10:00 AM - 7:00 PM IST"
    }
}

JOB_OPPORTUNITIES = [
    {
        "id": "job1",
        "title": "Frontend Developer",
        "department": "Engineering",
        "type": "Full-time",
        "location": "On-site",
        "description": "We're looking for an experienced Frontend Developer to join our team. Proficiency in React, Vue, or Angular required.",
        "requirements": [
            "3+ years of experience with modern JavaScript frameworks",
            "Strong HTML/CSS skills",
            "Experience with responsive design",
            "Knowledge of state management solutions"
        ],
        "benefits": [
            "Competitive salary",
            "Health insurance",
            "Flexible working hours",
            "Professional development budget"
        ]
    },
    {
        "id": "job2",
        "title": "Machine Learning Engineer",
        "department": "AI Research",
        "type": "Full-time",
        "location": "Remote",
        "description": "Join our AI team to develop cutting-edge machine learning solutions for real-world problems.",
        "requirements": [
            "MS or PhD in Computer Science or related field",
            "Experience with PyTorch or TensorFlow",
            "Strong understanding of ML algorithms",
            "Experience deploying ML models to production"
        ],
        "benefits": [
            "Top-tier compensation",
            "Remote-first culture",
            "Research publication opportunities",
            "Access to high-performance computing resources"
        ]
    }
]


# Pydantic models (unchanged)
class ServiceInquiry(BaseModel):
    name: str = Field(description="Customer's full name")
    email: str = Field(description="Customer's email address")
    service_id: str = Field(description="ID of the service")
    project_details: str = Field(description="Description of the project")

class JobApplication(BaseModel):
    name: str = Field(description="Applicant's full name")
    email: str = Field(description="Applicant's email address")
    job_id: str = Field(description="ID of the job")
    resume_link: str = Field(description="Link to resume")
    cover_letter: Optional[str] = Field(default=None, description="Optional cover letter")

# Base Tool class and tool implementations (unchanged)
class BaseTool:
    name: str
    description: str
    def _run(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement _run method")

class GetServicesListTool(BaseTool):
    name = "get_services_list"
    description = "Get the list of services offered by the company."
    def _run(self, query: Optional[str] = None) -> str:
        response = f"Here's what we offer at LogBinary:\n\n"
        for service in COMPANY_CONFIG["services"]:
            response += f"🔹 {service['name']}: {service['description']}\n"
        response += "\nWhich service sounds exciting to you? I can tell you more!"
        return response

class GetServiceDetailsTool(BaseTool):
    name = "get_service_details"
    description = "Get detailed information about a specific service"
    def _run(self, query: str) -> str:
        service_id = query
        service = next((s for s in COMPANY_CONFIG["services"] if s["id"] == service_id), None)
        if not service:
            return f"Sorry, I couldn't find information about the service with ID {service_id}."
        return f"{service['name']}: {service['description']}\n\n{service['details']}"

class GetJobsListTool(BaseTool):
    name = "get_jobs_list"
    description = "Get the list of current job openings at the company."
    def _run(self, query: Optional[str] = None) -> str:
        response = "Here are our current job openings at LogBinary:\n\n"
        for i, job in enumerate(JOB_OPPORTUNITIES, 1):
            response += f"{i}. {job['title']} ({job['department']}) - {job['type']}, {job['location']}\n"
        response += "\nWhich one interests you? Just say the number or title for more details!"
        return response

class GetJobDetailsTool(BaseTool):
    name = "get_job_details"
    description = "Get detailed information about a specific job opening."
    def _run(self, query: str) -> str:
        try:
            job_number = int(query.strip())
            if 1 <= job_number <= len(JOB_OPPORTUNITIES):
                job = JOB_OPPORTUNITIES[job_number - 1]
                return self._format_job_details(job)
        except ValueError:
            pass
        job = next((j for j in JOB_OPPORTUNITIES if j["id"].lower() == query.lower()), None)
        if job:
            return self._format_job_details(job)
        job = next((j for j in JOB_OPPORTUNITIES if query.lower() in j["title"].lower()), None)
        if job:
            return f"{self._format_job_details(job)}\n\nLike what you see? Ask me anything about it!"
        return f"Sorry, I couldn't find information about the job '{query}'. Please try again with a valid job title or number."
    
    def _format_job_details(self, job):
        details = f"📌 {job['title']} ({job['department']})\n"
        details += f"📍 {job['location']} | 🕒 {job['type']}\n\n"
        details += f"📝 Description:\n{job['description']}\n\n"
        details += "✅ Requirements:\n" + "\n".join(f"• {req}" for req in job['requirements']) + "\n"
        details += "💼 Benefits:\n" + "\n".join(f"• {benefit}" for benefit in job['benefits']) + "\n"
        details += "\nTo apply, provide your name, email, and resume link!"
        return details

class SubmitServiceInquiryTool(BaseTool):
    name = "submit_service_inquiry"
    description = "Submit a service inquiry from a potential customer."
    args_schema = ServiceInquiry
    def _run(self, name: str, email: str, service_id: str, project_details: str) -> str:
        service = next((s for s in COMPANY_CONFIG["services"] if s["id"] == service_id), None)
        if not service:
            return f"Sorry, I couldn't find the service with ID {service_id}."
        logger.info(f"Service inquiry submitted: {name}, {email}, {service['name']}, {project_details}")
        return f"Thank you, {name}! Your inquiry about {service['name']} has been submitted. We'll contact you at {email} soon."

class SubmitJobApplicationTool(BaseTool):
    name = "submit_job_application"
    description = "Submit a job application from a potential candidate"
    args_schema = JobApplication
    def _run(self, name: str, email: str, job_id: str, resume_link: str, cover_letter: Optional[str] = None) -> str:
        job = next((j for j in JOB_OPPORTUNITIES if j["id"] == job_id), None)
        if not job:
            return f"Sorry, I couldn't find the job with ID {job_id}."
        logger.info(f"Job application submitted: {name}, {email}, {job['title']}, {resume_link}")
        return f"Thank you, {name}! Your application for {job['title']} has been submitted. We'll review it and reach out to {email}."

class GetContactInfoTool(BaseTool):
    name = "get_contact_info"
    description = "Get the contact information for the company."
    def _run(self, query: Optional[str] = None) -> str:
        contact = COMPANY_CONFIG["contact_info"]
        return f"Here's how to reach us at LogBinary:\n\n- Email: {contact['email']}\n- Phone: {contact['phone']}\n- Hours: {contact['hours']}\n\nAnything else I can help with?"

# LLM Provider Classes (Updated for Groq)
class LLMProvider:
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
    def invoke(self, messages: List[Dict], functions: Optional[List] = None) -> Dict:
        raise NotImplementedError("Subclasses must implement invoke method")

class GroqLLM(LLMProvider):
    def __init__(self, model: str = "llama3-70b-8192", api_key: Optional[str] = None):
        super().__init__(model, api_key or GROQ_API_KEY)
        self.client = Groq(api_key=self.api_key)
    
    def invoke(self, messages: List[Dict], functions: Optional[List] = None) -> Dict:
        try:
            api_args = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 1024,
            }
            if functions:
                api_args["tools"] = [{"type": "function", "function": func} for func in functions]
            completion = self.client.chat.completions.create(**api_args)
            if not completion or not getattr(completion, "choices", None):
                logger.error("No choices returned in API response: %s", completion)
                return {"role": "assistant", "content": "I'm having trouble connecting to my services. Please try again in a moment."}
            return completion.choices[0].message
        except Exception as e:
            logger.error(f"Error calling Groq: {e}")
            logger.error(traceback.format_exc())
            return {"content": "I'm sorry, there was an error processing your request. Please try again.", "role": "assistant"}

def get_llm_provider() -> LLMProvider:
    if GROQ_API_KEY:
        return GroqLLM()
    raise ValueError("GROQ_API_KEY is not configured.")

def create_company_agent():
    llm = get_llm_provider()
    logger.info(f"Using LLM provider: {llm.__class__.__name__} with model {llm.model}")
    tools = [
        GetServicesListTool(), GetServiceDetailsTool(), GetJobsListTool(),
        GetJobDetailsTool(), SubmitServiceInquiryTool(), SubmitJobApplicationTool(),
        GetContactInfoTool()
    ]
    functions = [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": tool.args_schema.schema().get("properties", {"query": {"type": "string", "description": "Optional query string"}}) if hasattr(tool, 'args_schema') and tool.args_schema else {"query": {"type": "string"}},
                "required": tool.args_schema.schema().get("required", []) if hasattr(tool, 'args_schema') and tool.args_schema else []
            }
        } for tool in tools
    ]
    system_message = {
        "role": "system",
        "content": """
        # LogBinary AI Assistant

        You are LogBinary's dedicated AI assistant, designed to provide exceptional support to website visitors seeking information about our company offerings, career opportunities, and communication channels.

        ## Core Responsibilities

        - **Information Accuracy**: Always utilize designated data retrieval tools to ensure all provided information is current and correct
        - **Professional Representation**: Embody LogBinary's values of expertise, reliability, and client-centered service in every interaction
        - **Efficient Assistance**: Deliver clear, concise responses that address visitor inquiries with precision

        ## Interaction Guidelines

        When engaging with visitors, please:

        - Welcome new users with a brief, professional greeting that establishes a positive first impression
        - Maintain a warm yet professional tone that balances approachability with expertise
        - Focus responses on precisely addressing the query without unnecessary elaboration
        - Always provide fresh information when asked about services, jobs, or contact details, even if similar questions were asked before
        - Acknowledge when information falls outside your available resources rather than providing uncertain answers

        ## Information Retrieval Protocols

        For specific inquiries, always use the designated tools:
        - **Services Information**: GetServicesListTool tool for solution details and capabilities
        - **Career Opportunities**: jobs_lookup tool for current positions and requirements
        - **Contact Details**: contact_lookup tool for accurate communication channels

        When faced with specialized technical questions beyond available information, offer to connect visitors with appropriate LogBinary specialists.

        Your ultimate purpose is to deliver a seamless, informative experience that enhances LogBinary's professional reputation while efficiently addressing visitor needs.
        """
    }

    class CustomAgentExecutor:
        def __init__(self, llm, tools, system_message):
            self.llm = llm
            self.tools = {tool.name: tool for tool in tools}
            self.system_message = system_message
            self.memory = []
            self.functions = functions
        
        async def ainvoke(self, input_data):
            user_input = input_data.get("input", "")
            try:
                messages = [self.system_message] + self.memory + [{"role": "user", "content": user_input}]
                response = self.llm.invoke(messages=messages, functions=self.functions)
                logger.debug(f"Agent raw response: {response}")
                function_call = getattr(response, 'function_call', None)
                tool_calls = getattr(response, 'tool_calls', None)
                
                if function_call:
                    function_name = function_call.name
                    function_args = json.loads(function_call.arguments)
                    if function_name in self.tools:
                        tool_response = self.tools[function_name]._run(**function_args)
                        self.memory.append({"role": "user", "content": user_input})
                        self.memory.append({"role": "assistant", "content": tool_response})
                        return {"output": tool_response}  # Return tool output directly
                elif tool_calls:
                    tool_call = tool_calls[0]
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    if function_name in self.tools:
                        tool_response = self.tools[function_name]._run(**function_args)
                        self.memory.append({"role": "user", "content": user_input})
                        self.memory.append({"role": "assistant", "content": tool_response})
                        return {"output": tool_response}  # Return tool output directly
                
                # Fallback to natural language response
                output = response.content if hasattr(response, 'content') else response["content"]
                self.memory.append({"role": "user", "content": user_input})
                self.memory.append({"role": "assistant", "content": output})
                if len(self.memory) > 10:
                    self.memory = self.memory[-10:]
                return {"output": output}
            except Exception as e:
                logger.error(f"Error in agent invocation: {str(e)}")
                return {"output": "I'm sorry, I encountered an unexpected error. Please try again or contact our support team."}
    
    return CustomAgentExecutor(llm, tools, system_message)

class CompanyAIChatbot:
    def __init__(self):
        try:
            self.agent = create_company_agent()
            self.context = {"last_topic": None}
            logger.info("CompanyAIChatbot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CompanyAIChatbot: {str(e)}")
            raise

    async def process_message(self, user_message: str) -> str:
        try:
            user_message = user_message.strip().lower()
            if not user_message:
                return "Hello! How can I assist you today with LogBinary's services, job openings, or contact info?"

            # Check for m   ultiple topics
            has_services = "service" in user_message and not any(s["name"].lower() in user_message for s in COMPANY_CONFIG["services"])
            has_jobs = "job" in user_message or "opening" in user_message
            if has_services and has_jobs:
                services_response = GetServicesListTool()._run()
                jobs_response = GetJobsListTool()._run()
                return f"{services_response}\n\n{jobs_response}"

            # Service-related keywords
            service_keywords = {"python": "service1", "ml": "service2", "ai": "service2", "application": "service3", "app": "service3"}
            for keyword, service_id in service_keywords.items():
                if keyword in user_message and "service" not in user_message and "job" not in user_message:
                    details_tool = GetServiceDetailsTool()
                    return details_tool._run(service_id)

            # General services query
            if has_services:
                services_tool = GetServicesListTool()
                return services_tool._run()

            # Specific service query
            for service in COMPANY_CONFIG["services"]:
                if service["name"].lower() in user_message or service["id"] in user_message:
                    details_tool = GetServiceDetailsTool()
                    return details_tool._run(service["id"])

            # General jobs query
            if has_jobs:
                jobs_tool = GetJobsListTool()
                return jobs_tool._run()

            # Specific job query
            if user_message in ["1", "2"]:
                details_tool = GetJobDetailsTool()
                return details_tool._run(user_message)
            for job in JOB_OPPORTUNITIES:
                if job["title"].lower() in user_message or job["id"] in user_message:
                    details_tool = GetJobDetailsTool()
                    return details_tool._run(job["id"])

            # Fallback to agent
            response = await self.agent.ainvoke({"input": user_message})
            return response["output"]
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "Oops, something went wrong! How about asking me about our services, jobs, or contact info?"

# FastAPI App
app = FastAPI(title="LogBinary AI Chatbot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_homepage():
    try:
        return FileResponse("index_234.html")
    except FileNotFoundError:
        create_test_html()
        return FileResponse("index_234.html")

@app.get("/health")
async def health_check():
    try:
        llm = get_llm_provider()
        return {"status": "healthy", "llm_provider": llm.__class__.__name__, "model": llm.model}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Service unhealthy: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        chatbot = CompanyAIChatbot()
        welcome_message = "Hi there! 👋 I'm LogBinary's virtual assistant. How can I help you today?"
        await websocket.send_text(welcome_message)
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message: {data}")
            
            # Send typing indicator
            await websocket.send_text("Typing...")
            
            # Process message if not in cache
            response = await chatbot.process_message(data)
            
            # Small delay to simulate typing
            await asyncio.sleep(0.5)
            
            logger.info(f"Sending response: {response[:100]}...")
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error in websocket: {e}")
        logger.error(traceback.format_exc())
        try:
            await websocket.send_text("I'm having trouble processing your request. Please try again or contact our support team directly.")
        except:
            logger.error("Failed to send error message")

# Helper function to create a simple HTML file for testing
def create_test_html():
    html = """
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LogBinary AI Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }
        body {
            background-color: #f9fafb;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .chat-widget {
            width: 400px;
            height: 650px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .chat-header {
            background-color: #4f46e5;
            padding: 16px 20px;
            color: white;
            display: flex;
            align-items: center;
        }
        .assistant-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: linear-gradient(135deg, #4f46e5, #a855f7);
            display: flex;
            justify-content: center;
            align-items: center;
            margin-right: 12px;
        }
        .assistant-avatar svg {
            width: 20px;
            height: 20px;
            color: white;
        }
        .header-text {
            flex-grow: 1;
        }
        .header-text h1 {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
        }
        .status-badge {
            margin-left: 8px;
            background-color: rgba(255, 255, 255, 0.2);
            color: white;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 500;
        }
        .header-text p {
            font-size: 13px;
            opacity: 0.9;
        }
        .close-button {
            width: 24px;
            height: 24px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            cursor: pointer;
        }
        .close-button span {
            color: white;
            font-size: 14px;
            line-height: 1;
        }
        .conversation {
            flex-grow: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .message {
            display: flex;
            align-items: flex-start;
            max-width: 85%;
        }
        .user-message {
            justify-content: flex-end;
            margin-left: auto;
        }
        .bot-message {
            justify-content: flex-start;
        }
        .message-bubble {
            padding: 12px 16px;
            border-radius: 18px;
            font-size: 14px;
            line-height: 1.5;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .user-message .message-bubble {
            background-color: #4f46e5;
            color: white;
            border-bottom-right-radius: 4px;
        }
        .bot-message .message-bubble {
            background-color: #f3f4f6;
            color: #374151;
            border-bottom-left-radius: 4px;
        }
        .bot-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: linear-gradient(135deg, #4f46e5, #a855f7);
            display: flex;
            justify-content: center;
            align-items: center;
            margin-right: 8px;
            flex-shrink: 0;
        }
        .bot-avatar svg {
            width: 16px;
            height: 16px;
            color: white;
        }
        .user-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: #e5e7eb;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-left: 8px;
            flex-shrink: 0;
        }
        .user-avatar svg {
            width: 16px;
            height: 16px;
            color: #6b7280;
        }
        .input-container {
            padding: 16px;
            border-top: 1px solid #e5e7eb;
        }
        .input-wrapper {
            display: flex;
            align-items: center;
            background-color: #f3f4f6;
            border-radius: 24px;
            padding: 8px 16px;
            transition: all 0.2s ease;
        }
        .input-wrapper:focus-within {
            box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.3);
            background-color: white;
        }
        #message-input {
            flex-grow: 1;
            border: none;
            outline: none;
            background: transparent;
            padding: 8px 0;
            font-size: 14px;
            color: #374151;
        }
        #message-input::placeholder {
            color: #9ca3af;
        }
        #send-button {
            width: 36px;
            height: 36px;
            background-color: #4f46e5;
            border-radius: 50%;
            border: none;
            display: flex;
            justify-content: center;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        #send-button:hover {
            background-color: #4338ca;
        }
        .footer {
            padding: 12px 16px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            border-top: 1px solid #f3f4f6;
        }
        .footer a {
            color: #4f46e5;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        
        /* Updated styles for preset questions */
        .preset-questions-container {
            margin-top: 12px;
            position: sticky;
            bottom: 0;
            background: white;
            padding: 12px 16px;
            border-top: 1px solid #e5e7eb;
        }
        .preset-questions {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .preset-question-button {
            background-color: #f0f7ff;
            border: 1px solid #dbeafe;
            color: #4f46e5;
            border-radius: 20px;
            padding: 10px 16px;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        .preset-question-button:hover {
            background-color: #e0f2fe;
            border-color: #bfdbfe;
            transform: translateY(-1px);
            box-shadow: 0 3px 6px rgba(0, 0, 0, 0.1);
        }
        .preset-question-button:active {
            transform: translateY(0);
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
        }
    </style>
</head>
<body>
    <div class="chat-widget">
        <div class="chat-header">
            <div class="assistant-avatar">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
            </div>
            <div class="header-text">
                <h1>Ask LogBinary <span class="status-badge">online</span></h1>
            </div>
            <div class="close-button">
                <span>✕</span>
            </div>
        </div>
        
        <div id="chat-box" class="conversation"></div>
        
        <div class="input-container">
            <div class="input-wrapper">
                <input type="text" id="message-input" placeholder="Ask about services, jobs, or contact...">
                <button id="send-button">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="white" viewBox="0 0 16 16">
                        <path d="M15.964.686a.5.5 0 0 0-.65-.65L.767 5.855H.766l-.452.18a.5.5 0 0 0-.082.887l.41.26.001.002 4.995 3.178 3.178 4.995.002.002.26.41a.5.5 0 0 0 .886-.083l6-15Zm-1.833 1.89L6.637 10.07l-.215-.338a.5.5 0 0 0-.154-.154l-.338-.215 7.494-7.494 1.178-.471-.47 1.178Z"/>
                    </svg>
                </button>
            </div>
        </div>
        
        <div class="footer">
            By using this assistant, you agree to our <a href="#">Terms & Privacy</a>
        </div>
    </div>

    <script>
        const chatBox = document.getElementById('chat-box');
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');
        
        // Connect to WebSocket
        const socket = new WebSocket('ws://' + window.location.host + '/ws');
        let isFirstMessage = true;
        
        socket.onopen = function(e) {
            console.log('WebSocket connection established');
        };
        
        socket.onmessage = function(event) {
            console.log("Received message:", event.data);
            
            // If this is the first message (welcome message), add preset questions after it
            if (isFirstMessage && event.data !== "Typing...") {
                addBotMessage(event.data);
                addPresetQuestions();
                isFirstMessage = false;
            } else if (event.data !== "Typing...") {
                addBotMessage(event.data);
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
                
                // Show typing indicator
                showTypingIndicator();
            }
        }
        
        function addUserMessage(message) {
            const messageElement = document.createElement('div');
            messageElement.classList.add('message', 'user-message');
            
            messageElement.innerHTML = `
                <div class="message-bubble">${message}</div>
                <div class="user-avatar">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                </div>
            `;
            
            chatBox.appendChild(messageElement);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        
        function addBotMessage(message) {
            // Remove typing indicator if it exists
            const typingIndicator = document.getElementById('typing-indicator');
            if (typingIndicator) typingIndicator.remove();
            
            if (message !== "Typing...") {
                const messageElement = document.createElement('div');
                messageElement.classList.add('message', 'bot-message');
                
                messageElement.innerHTML = `
                    <div class="bot-avatar">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                    </div>
                    <div class="message-bubble">${message}</div>
                `;
                
                chatBox.appendChild(messageElement);
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }
        
        function showTypingIndicator() {
            const typingElement = document.createElement('div');
            typingElement.classList.add('message', 'bot-message');
            typingElement.id = 'typing-indicator';
            
            typingElement.innerHTML = `
                <div class="bot-avatar">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                </div>
                <div class="message-bubble">Typing...</div>
            `;
            
            chatBox.appendChild(typingElement);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        
        function addPresetQuestions() {
    // Create preset questions container without the bot avatar
    const presetContainer = document.createElement('div');
    presetContainer.id = 'preset-questions-container';
    presetContainer.classList.add('preset-questions-container');
    
    presetContainer.innerHTML = `
        <div class="preset-questions">
            <button class="preset-question-button" data-question="I want to learn about LogBinary's services">I want to learn about LogBinary's services</button>
            <button class="preset-question-button" data-question="I want to know about job openings">I want to know about job openings</button>
            <button class="preset-question-button" data-question="I need LogBinary's contact details">I need LogBinary's contact details</button>
        </div>
    `;
    
    chatBox.appendChild(presetContainer);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    // Add event listeners to preset question buttons
    const presetButtons = presetContainer.querySelectorAll('.preset-question-button');
    presetButtons.forEach(button => {
        button.addEventListener('click', function() {
            const question = this.getAttribute('data-question');
            addUserMessage(question);
            socket.send(question);
            showTypingIndicator();
            
            // Remove the preset questions container after a button is clicked
            const presetContainer = document.getElementById('preset-questions-container');
            if (presetContainer) {
                presetContainer.remove();
            }
        });
    });
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

