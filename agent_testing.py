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
from groq import Groq
import csv
import re
from datetime import datetime

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
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not found in environment variables, using fallback method")
    GROQ_API_KEY = "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"

def load_company_data():
    """Load company data from CSV files"""
    company_data = {
        "company_name": "LogBinary",
        "services": [],
        "careers": [],
        "contact_info": {}
    }
    
    if os.path.exists("services.csv"):
        with open("services.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            company_data["services"] = list(reader)
    else:
        logger.warning("services.csv file not found")
    
    if os.path.exists("jobs.csv"):
        with open("jobs.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            jobs = []
            for row in reader:
                if "requirements" in row:
                    row["requirements"] = row["requirements"].split(",")
                if "benefits" in row:
                    row["benefits"] = row["benefits"].split(",")
                jobs.append(row)
            company_data["careers"] = jobs
    else:
        logger.warning("jobs.csv file not found")
    
    if os.path.exists("contact_info.csv"):
        with open("contact_info.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company_data["contact_info"][row["key"]] = row["value"]
    else:
        logger.warning("contact_info.csv file not found")
    
    return company_data

COMPANY_DATA = load_company_data()
COMPANY_CONFIG = COMPANY_DATA
JOB_OPPORTUNITIES = COMPANY_DATA["careers"]

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

class BaseTool:
    name: str
    description: str
    def _run(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement _run method")

class GetServicesListTool(BaseTool):
    name = "get_services_list"
    description = "Retrieve the list of services offered by LogBinary as raw data."
    def _run(self, query: Optional[str] = None) -> List[Dict]:
        return COMPANY_CONFIG["services"]

class GetServiceDetailsTool(BaseTool):
    name = "get_service_details"
    description = "Retrieve detailed information about a specific service by its ID."
    def _run(self, query: str) -> Dict:
        service_id = query
        service = next((s for s in COMPANY_CONFIG["services"] if s["id"] == service_id), None)
        if not service:
            return {"error": f"Service with ID {service_id} not found."}
        return service

class GetJobsListTool(BaseTool):
    name = "get_jobs_list"
    description = "Retrieve the list of current job openings at LogBinary as raw data."
    def _run(self, query: Optional[str] = None) -> List[Dict]:
        return JOB_OPPORTUNITIES

class GetJobDetailsTool(BaseTool):
    name = "get_job_details"
    description = "Retrieve detailed information about a specific job opening by its ID or number."
    def _run(self, query: str) -> Dict:
        try:
            job_number = int(query.strip())
            if 1 <= job_number <= len(JOB_OPPORTUNITIES):
                return JOB_OPPORTUNITIES[job_number - 1]
        except ValueError:
            pass
        job = next((j for j in JOB_OPPORTUNITIES if j["id"].lower() == query.lower()), None)
        if job:
            return job
        job = next((j for j in JOB_OPPORTUNITIES if query.lower() in j["title"].lower()), None)
        if job:
            return job
        return {"error": f"Job '{query}' not found."}

class SubmitServiceInquiryTool(BaseTool):
    name = "submit_service_inquiry"
    description = "Submit a general inquiry from a potential customer and save to CSV."
    # Update args_schema if validation is needed (optional)
    # args_schema = ServiceInquiry  # You can redefine this model or remove it if not needed

    def _run(self, name: str, email: str, phone: str, subject: str, message: str) -> Dict:
        # No service lookup needed since it's a general inquiry
        # Save to CSV
        csv_file = "service_inquiries.csv"
        fieldnames = ["name", "email", "phone", "subject", "message", "timestamp"]
        inquiry_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "subject": subject,
            "message": message,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        file_exists = os.path.exists(csv_file)
        with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(inquiry_data)
        
        logger.info(f"General inquiry submitted and saved: {name}, {email}, {subject}, {message}")
        return {
            "status": "success",
            "name": name,
            "email": email,
            "subject": subject
        }

class SubmitJobApplicationTool(BaseTool):
    name = "submit_job_application"
    description = "Submit a job application from a potential candidate and return confirmation data."
    args_schema = JobApplication
    def _run(self, name: str, email: str, job_id: str, resume_link: str, cover_letter: Optional[str] = None) -> Dict:
        job = next((j for j in JOB_OPPORTUNITIES if j["id"] == job_id), None)
        if not job:
            return {"error": f"Job with ID {job_id} not found."}
        logger.info(f"Job application submitted: {name}, {email}, {job['title']}, {resume_link}")
        return {
            "status": "success",
            "name": name,
            "email": email,
            "job_title": job["title"]
        }

class GetContactInfoTool(BaseTool):
    name = "get_contact_info"
    description = "Retrieve the contact information for LogBinary as raw data."
    def _run(self, query: Optional[str] = None) -> Dict:
        return COMPANY_CONFIG["contact_info"]

class LLMProvider:
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
    def invoke(self, messages: List[Dict], functions: Optional[List] = None) -> Dict:
        raise NotImplementedError("Subclasses must implement invoke method")

class GroqLLM(LLMProvider):
    def __init__(
        self, 
        model: str = "gemma2-9b-it", 
        api_key: Optional[str] = None,
        fallback_models: Optional[List[str]] = None
    ):
        super().__init__(model, api_key or GROQ_API_KEY)
        self.client = Groq(api_key=self.api_key)
        self.fallback_models = fallback_models or ["qwen-2.5-32b", "llama3-70b-8192"]
        self.current_model_index = 0
        self.models = [model] + self.fallback_models
    
    def _get_current_model(self) -> str:
        return self.models[self.current_model_index]
    
    def _try_next_model(self) -> bool:
        """Try switching to the next model in the fallback list.
        Returns True if successfully switched, False if no more models to try."""
        if self.current_model_index < len(self.models) - 1:
            self.current_model_index += 1
            logger.info(f"Switching to fallback model: {self._get_current_model()}")
            return True
        return False
    
    def invoke(self, messages: List[Dict], functions: Optional[List] = None) -> Dict:
        attempts = 0
        max_attempts = len(self.models)
        
        while attempts < max_attempts:
            try:
                current_model = self._get_current_model()
                logger.info(f"Attempting request with model: {current_model}")
                
                api_args = {
                    "model": current_model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                }
                
                if functions:
                    api_args["tools"] = [{"type": "function", "function": func} for func in functions]
                
                completion = self.client.chat.completions.create(**api_args)
                
                if not completion or not getattr(completion, "choices", None):
                    logger.error(f"No choices returned in API response for model {current_model}: {completion}")
                    if not self._try_next_model():
                        return {"role": "assistant", "content": "I'm having trouble connecting to my services. Please try again in a moment."}
                else:
                    # Success! Reset to preferred model for next call
                    if self.current_model_index > 0:
                        self.current_model_index = 0
                    return completion.choices[0].message
                    
            except Exception as e:
                error_message = str(e).lower()
                attempts += 1
                
                # Check for rate limit or quota-related errors
                if any(term in error_message for term in ["rate limit", "quota", "capacity", "too many requests", "429"]):
                    logger.warning(f"Rate limit hit for model {self._get_current_model()}: {e}")
                    if not self._try_next_model():
                        logger.error("All models exhausted. No more fallbacks available.")
                        break
                else:
                    # For other errors, log and break the retry loop
                    logger.error(f"Error calling Groq with model {self._get_current_model()}: {e}")
                    logger.error(traceback.format_exc())
                    break
        
        return {"content": "I'm sorry, there was an error processing your request. Please try again later.", "role": "assistant"}

def get_llm_provider() -> LLMProvider:
    try:
        return GroqLLM()
    except Exception as e:
        logger.error(f"Failed to initialize Groq LLM: {e}")
        raise ValueError("Failed to initialize any LLM provider.")

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

        - **Information Accuracy**: Always utilize designated data retrieval tools to fetch current and correct information when required, except for company info which is provided below.
        - **Professional Representation**: Embody LogBinary's values of expertise, reliability, and client-centered service in every interaction.
        - **Efficient Assistance**: Deliver clear, concise responses that address visitor inquiries with precision.

        ## Interaction Guidelines

        When engaging with visitors, please:

        - Welcome new users with a brief, professional greeting that establishes a positive first impression. Avoid followup with the services details. Avoid listing services unless explicitly asked.
        - Maintain a warm yet professional tone that balances approachability with expertise.
        - Focus responses on precisely addressing the query without unnecessary elaboration.
        - Always fetch fresh information using tools when asked about services, jobs, or contact details, even if similar questions were asked before.
        - Acknowledge when information falls outside your available resources rather than providing uncertain answers.
        - When a visitor expresses interest in services (e.g., says 'interested in ' or similar), immediately generate an HTML form to collect their details using the `submit_service_inquiry` tool, even if no specific service is mentioned. Use the first service from `get_services_list` as the default `service_id` if none is specified.

        ## Company Information

        When a user asks about "logbinary," "the company," "LB," or phrases like "tell me about LogBinary" or "what is LogBinary,"(it is not case sensitive) respond with the following exact text:

        "We are a comprehensive IT solutions provider dedicated to transforming business ideas into reality through cutting-edge software technologies. With 15 years of proven industry expertise, we have a deep understanding of what businesses need to thrive in a competitive landscape. Our commitment lies in delivering high-quality websites and mobile applications that empower our clients to achieve operational excellence and drive profitability."

        Do not use tools for this response unless the user asks for additional details beyond this description.

        ## Information Retrieval Protocols

        For specific inquiries beyond company info, always use the designated tools:
        - **Services Information**: Use `get_services_list` for a list of services only no details, and `get_service_details` for details about a specific service.
        - **Career Opportunities**: Use `get_jobs_list` for current positions/openings only don’t add details, and `get_job_details` for details about a specific job.
        - **Contact Details**: Use `get_contact_info` for accurate communication channels.
    
        ## Service Inquiry Submission Protocol
    
        - When a visitor expresses interest in a specific service, generate an HTML form with fields for:
          - First name
          - Last name
          - Phone number
          - Business email
          - Job role
          - Country/Region
          - Project details
        - If no specific service is mentioned, use the first service from `get_services_list` as the default `service_id`.
        - Include a submit button to send the form data back via WebSocket.
        - Upon submission, use the `submit_service_inquiry` tool to save the data to a CSV file.

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
            self.max_retries = 2
        
        async def ainvoke(self, input_data):
            user_input = input_data.get("input", "")
            for retry in range(self.max_retries + 1):
                try:
                    messages = [self.system_message] + self.memory + [{"role": "user", "content": user_input}]
                    response = self.llm.invoke(messages=messages, functions=self.functions)
                    logger.debug(f"Agent raw response: {response}")
                    
                    function_calls = []
                    if hasattr(response, 'function_call') and response.function_call:
                        function_calls.append({
                            'name': response.function_call.name,
                            'arguments': response.function_call.arguments
                        })
                    elif hasattr(response, 'tool_calls') and response.tool_calls:
                        for tool_call in response.tool_calls:
                            function_calls.append({
                                'name': tool_call.function.name,
                                'arguments': tool_call.function.arguments
                            })
                    elif isinstance(response, dict):
                        if response.get('function_call'):
                            function_calls.append({
                                'name': response['function_call']['name'],
                                'arguments': response['function_call']['arguments']
                            })
                        elif response.get('tool_calls'):
                            for tool_call in response['tool_calls']:
                                function_calls.append({
                                    'name': tool_call['function']['name'],
                                    'arguments': tool_call['function']['arguments']
                                })
                    
                    if function_calls:
                        tool_responses = []
                        for fc in function_calls:
                            function_name = fc['name']
                            try:
                                function_args = json.loads(fc['arguments'])
                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse function arguments: {fc['arguments']}")
                                function_args = {}
                                
                            if function_name in self.tools:
                                tool_response = self.tools[function_name]._run(**function_args)
                                tool_responses.append({
                                    "role": "function", 
                                    "name": function_name, 
                                    "content": json.dumps(tool_response)
                                })
                        
                        if tool_responses:
                            messages.extend(tool_responses)
                            final_response = self.llm.invoke(messages=messages)
                            output = final_response.get('content') if isinstance(final_response, dict) else getattr(final_response, 'content', "I'm having trouble processing that request.")
                            self.memory.append({"role": "user", "content": user_input})
                            self.memory.append({"role": "assistant", "content": output})
                            if len(self.memory) > 10:
                                self.memory = self.memory[-10:]
                            return {"output": output}
                    
                    output = response.get('content') if isinstance(response, dict) else getattr(response, 'content', "I'm having trouble understanding right now.")
                    self.memory.append({"role": "user", "content": user_input})
                    self.memory.append({"role": "assistant", "content": output})
                    if len(self.memory) > 10:
                        self.memory = self.memory[-10:]
                    return {"output": output}
                    
                except Exception as e:
                    logger.error(f"Error in agent invocation (attempt {retry+1}/{self.max_retries+1}): {str(e)}")
                    if retry < self.max_retries:
                        logger.info(f"Retrying agent invocation...")
                        await asyncio.sleep(1)
                    else:
                        return {"output": "I'm sorry, I encountered an unexpected error. Please try again or contact our support team."}

    return CustomAgentExecutor(llm, tools, system_message)

class CompanyAIChatbot:
    def __init__(self):
        try:
            self.agent = create_company_agent()
            self.context = {"last_topic": None}
            self.chat_styles = """
            <style>
            .section-header {
                font-weight: 600;
                color: #0972d3;
                margin-top: 12px;
                margin-bottom: 6px;
            }
            .highlight {
                color: #0972d3;
                font-weight: 600;
            }
            .styled-list {
                list-style-type: none;
                padding-left: 12px;
                margin: 8px 0;
            }
            .bullet-item {
                position: relative;
                padding-left: 20px;
                margin-bottom: 8px;
                line-height: 1.4;
            }
            .bullet-item:before {
                content: "•";
                color: #0972d3;
                font-weight: bold;
                position: absolute;
                left: 0;
            }
            .key-offering {
                font-weight: 600;
                color: #232f3e;
                margin-top: 10px;
                margin-bottom: 4px;
            }
            .contact-label {
                font-weight: 600;
                color: #0972d3;
            }
            .paragraph-break {
                height: 12px;
            }
            .prompt-question {
                margin-top: 16px;
                font-style: italic;
                color: #545b64;
            }
            .inquiry-form {
                border: 1px solid #e9ebed;
                border-radius: 8px;
                padding: 16px;
                background-color: #f8f9fa;
                margin: 12px 0;
            }
            .form-group {
                margin-bottom: 12px;
            }
            .form-group label {
                font-weight: 600;
                color: #232f3e;
                display: block;
                margin-bottom: 4px;
            }
            .form-group input, .form-group select, .form-group textarea {
                width: 100%;
                padding: 8px;
                border: 1px solid #d9d9d9;
                border-radius: 4px;
                box-sizing: border-box;
            }
            .form-group input[type="submit"] {
                background-color: #0972d3;
                color: white;
                border: none;
                cursor: pointer;
                padding: 10px 20px;
            }
            .form-group input[type="submit"]:hover {
                background-color: #075aad;
            }
            </style>
            """
            logger.info("CompanyAIChatbot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CompanyAIChatbot: {str(e)}")
            raise

    async def process_message(self, user_message: str) -> str:
        try:
            user_message = user_message.strip()
            
            if not user_message:
                return f"""
                {self.chat_styles}
                <div class="welcome-message">
                    Hi there! 👋 <strong class="highlight">I'm LogBinary's virtual assistant</strong>. How can I help you today?
                </div>
                """

            # Check for service inquiry intent
            if "interested in" in user_message.lower() and any(s in user_message.lower() for s in ["service", "help", "offering"]):
                services_tool = next((t for t in self.agent.tools.values() if t.name == "get_services_list"), None)
                if services_tool:
                    services = services_tool._run()
                    service_id = None
                    service_name = None
                    for service in services:
                        if service["name"].lower() in user_message.lower() or (service.get("id") and service.get("id").lower() in user_message.lower()):
                            service_id = service["id"]
                            service_name = service["name"]
                            break
                    
                    # Default to first service if none specified
                    if not service_id and services:
                        service_id = services[0]["id"]
                        service_name = services[0]["name"]
                    
                    if service_id:
                        form_html = f"""
                        {self.chat_styles}
                        <div class="inquiry-form">
                            <p>Please input your business details. We are here for Perfect Solutions For Your Business!</p>
                            <form id="inquiryForm" data-service-id="{service_id}">
                                <div class="form-group">
                                    <label for="your">Your name</label>
                                    <input type="text" id="Your" name="Your_name" required>
                                </div>
                                <div class="form-group">
                                    <label for="phone">Phone number</label>
                                    <input type="tel" id="phone" name="phone" required>
                                </div>
                                <div class="form-group">
                                    <label for="email">Business email</label>
                                    <input type="email" id="email" name="email" required>
                                </div>
                                <div class="form-group">
                                    <label for="job_role">Subject</label>
                                    <input type="text" id="Subject" name="Subject" required>
                                </div>
                                <div class="form-group">
                                    <label for="project_details">Message</label>
                                    <textarea id="Message" name="Message" rows="4" required></textarea>
                                </div>
                                <div class="form-group">
                                    <input type="submit" value="Submit">
                                </div>
                            </form>
                            <p>By submitting, you acknowledge LogBinary collects and handles your information as described in our <a href="#">Privacy Notice</a>.</p>
                        </div>
                        <script>
                        document.getElementById('inquiryForm').addEventListener('submit', async function(e) {{
                            e.preventDefault(); // Prevent default form submission
                            console.log('Form submission triggered');
                            const formData = new FormData(this);
                            const data = Object.fromEntries(formData);
                            data.service_id = this.dataset.serviceId;
                            const fullName = `${{data.first_name}} ${{data.last_name}}`;
                            await socket.send(JSON.stringify({{ action: 'submit_inquiry', data: {{ ...data, name: fullName }} }}));
                            this.reset();
                            console.log('Form data sent:', {{ action: 'submit_inquiry', data: {{ ...data, name: fullName }} }});
                            return false;
                        }});
                        </script>
                        """
                        return form_html

            response = await self.agent.ainvoke({"input": user_message})
            output = response["output"]
            output = self.clean_markdown(output)
            
            if "I'm LogBinary's virtual assistant" in output:
                output = self.chat_styles + output
            
            return output
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "Oops, something went wrong! How about asking me about our services, jobs, or contact info?"
    
    def clean_markdown(self, text):
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        return text

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
        logger.error(f"Health check failed: {e}")        
        raise HTTPException(status_code=500, detail=f"Service unhealthy: {e}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        chatbot = CompanyAIChatbot()
        welcome_message = f"""
        {chatbot.chat_styles}
        <div class="welcome-message">
            Hi there! 👋 <strong class="highlight">I'm LogBinary's virtual assistant</strong>. How can I help you today?
        </div>
        """
        await websocket.send_text(welcome_message)
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message: {data}")
            
            await websocket.send_text("Typing...")
            
            if data.startswith('{') and data.endswith('}'):
                try:
                    message_data = json.loads(data)
                    if message_data.get("action") == "submit_inquiry":
                        inquiry_data = message_data["data"]
                        tool = next(t for t in chatbot.agent.tools.values() if t.name == "submit_service_inquiry")
                        result = tool._run(
                            name=inquiry_data.get("Your_name", inquiry_data.get("name", "")),  # Handle both cases
                            email=inquiry_data["email"],
                            phone=inquiry_data["phone"],
                            subject=inquiry_data["Subject"],  # Use capitalized "Subject" as sent by form
                            message=inquiry_data["Message"]   # Use capitalized "Message" as sent by form
                        )
                        continue
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
            
            response = await chatbot.process_message(data)
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
            background-color: #f8f9fa;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .chat-widget {
            width: 400px;
            height: 650px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border: 1px solid #d9d9d9;
        }
        .chat-header {
            background-color: #ffffff;
            padding: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #d9d9d9;
        }
        .header-left {
            display: flex;
            align-items: center;
        }
        .built-in-badge {
            background-color: #f2f3f3;
            border: 1px solid #d9d9d9;
            border-radius: 12px;
            padding: 2px 8px;
            font-size: 12px;
            margin-left: 8px;
            color: #232f3e;
        }
        .header-title {
            font-size: 16px;
            font-weight: 600;
            color: #232f3e;
            display: flex;
            align-items: center;
        }
        .header-controls {
            display: flex;
            gap: 8px;
        }
        .control-button {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 18px;
            color: #545b64;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
        }
        .status-message {
            padding: 8px 16px;
            background-color: #f8f8f8;
            border-bottom: 1px solid #d9d9d9;
            font-size: 12px;
            color: #545b64;
            display: flex;
            align-items: center;
        }
        .status-icon {
            width: 8px;
            height: 8px;
            background-color: #2cbb5d;
            border-radius: 50%;
            margin-right: 6px;
        }
        .conversation {
            flex-grow: 1;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            background-color: #ffffff;
        }
        .message {
            display: flex;
            max-width: 100%;
        }
        .user-message {
            justify-content: flex-end;
        }
        .bot-message {
            justify-content: flex-start;
        }
        .avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-right: 12px;
            flex-shrink: 0;
        }
        .bot-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background-color: #7558F7;
            display: flex;
            justify-content: center;
            align-items: center;
            flex-shrink: 0;
        }
        .bot-avatar svg {
            width: 16px;
            height: 16px;
            color: white;
        }
        .user-avatar {
            background-color: #e9ebed;
        }
        .message-content {
            max-width: calc(100% - 44px);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .message-bubble {
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.5;
            color: #232f3e;
            width: auto;
            display: inline-block;
        }
        .user-message .message-bubble {
            background-color: #f2f3f3;
        }
        .bot-message .message-bubble {
            background-color: #f8f9fa;
            border: 1px solid #e9ebed;
        }
        .suggestion-container {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .suggestion-buttons {
            display: flex;
            flex-direction: column;
            gap: 8px;
            width: 100%;
            align-items: flex-start;
        }
        .suggestion-button {
            background-color: #e6e6fa;
            border: none;
            color: #161d26;
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 14px;
            line-height: 1.5;
            text-align: left;
            cursor: pointer;
            transition: background-color 0.2s ease;
            width: auto;
            display: inline-block;
        }
        .suggestion-button:hover {
            background-color: #dadaf8;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
        }
        .input-container {
            padding: 6px;
            background-color: white;
            border-top: 1px solid #d9d9d9;
        }
        .input-wrapper {
            display: flex;
            align-items: center;
            background-color: white;
            border: 1px solid #d9d9d9;
            border-radius: 9px;
            padding: 4px 12px;
            transition: all 0.2s ease;
        }
        .input-wrapper:focus-within {
            box-shadow: 0 0 0 2px rgba(9, 114, 211, 0.3);
            border-color: #0972d3;
        }
        #message-input {
            flex-grow: 1;
            border: none;
            outline: none;
            background: transparent;
            padding: 4px 10px;
            font-size: 15px;
            color: #232f3e;
        }
        #message-input::placeholder {
            color: #687078;
        }
        #send-button {
            width: 32px;
            height: 32px;
            background-color: #7558F7;
            border-radius: 50%;
            border: none;
            display: flex;
            justify-content: center;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        #send-button:disabled {
            background-color: #e9ebed;
            cursor: not-allowed;
        }
        .footer {
            padding: 12px 16px;
            text-align: center;
            font-size: 12px;
            color: #687078;
        }
        .footer a {
            color: #0972d3;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        .arrow-icon {
            color: white;
        }
        @media (max-width: 480px) {
            .chat-widget {
                width: 95%;
                height: 90vh;
                border-radius: 4px;
            }
        }
    </style>
</head>
<body>
    <div class="chat-widget">
        <div class="chat-header">
            <div class="header-left">
                <span class="header-title">Ask LogBinary</span>
                <span class="built-in-badge">built-in</span>
            </div>
            <div class="header-controls">
                <button class="control-button">−</button>
                <button class="control-button">×</button>
            </div>
        </div>
        
        <div class="status-message">
            <span class="status-icon"></span>
            Our sales reps are online
        </div>
        
        <div id="chat-box" class="conversation"></div>
        
        <div class="input-container">
            <div class="input-wrapper">
                <input type="text" id="message-input" placeholder="Ask a question">
                <button id="send-button">
                    <svg class="arrow-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13"></line>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                    </svg>
                </button>
            </div>
        </div>
        
        <div class="footer">
            By chatting, you agree to this <a href="#">disclaimer</a>.
        </div>
    </div>

   <script>
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
                data.service_id = this.dataset.serviceId;
                const fullName = `${data.first_name} ${data.last_name}`;
                await socket.send(JSON.stringify({ action: 'submit_inquiry', data: { ...data, name: fullName } }));
                // Replace the form with the thank you message
                const parentMessage = this.closest('.message');
                if (parentMessage && !parentMessage.querySelector('.message-bubble').innerHTML.includes('Thank you!')) {
                    parentMessage.querySelector('.message-bubble').innerHTML = 'Thank you! Your record has been submitted. Is there anything else we can help you with?';
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
        }
        
        .bot-message .message-bubble {
            background-color: #f8f9fa;
            border: 1px solid #e9ebed;
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
        }
    `;
    document.head.appendChild(styleElement);
}

window.addEventListener('DOMContentLoaded', addGlobalStyles);

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
</script>
</body>
</html>
    """
    
    with open("index_234.html", "w") as file:
        file.write(html)

import datetime
create_test_html()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6440)