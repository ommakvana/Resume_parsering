import asyncio
from agent import create_company_agent
from config import logger

class CompanyAIChatbot:
    def __init__(self):
        self.context = {"last_topic": None, "last_job_discussed": None}
        try:
            self.agent = create_company_agent()
            self.context = {"last_topic": None}
            self.chat_styles = """
            <style>
                .chat-container {
                    font-family: Arial, sans-serif; /* Consistent font */
                    font-size: 14px; /* Consistent size */
                    color: #232f3e; /* Consistent text color */
                    line-height: 1.5;
                }
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
                .service-title, .job-title {
                    font-weight: 600;
                    color: #232f3e;
                }
                .service-desc, .job-desc {
                    font-style: italic;
                    color: #545b64;
                    margin-left: 20px;
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
                .form-group input, .form-group textarea {
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
                .prompt-question {
                    margin-top: 16px;
                    font-style: italic;
                    color: #545b64;
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

            # Handle WebSocket form submission
            if isinstance(user_message, dict) and user_message.get("action") == "submit_inquiry":
                inquiry_data = user_message.get("data", {})
                submit_tool = next((t for t in self.agent.tools.values() if t.name == "submit_service_inquiry"), None)
                if submit_tool and all(key in inquiry_data for key in ["name", "email", "phone", "subject", "message"]):
                    result = submit_tool._run(
                        name=inquiry_data["name"],
                        email=inquiry_data["email"],
                        phone=inquiry_data["phone"],
                        subject=inquiry_data["subject"],
                        message=inquiry_data["message"],
                        service_id=inquiry_data.get("service_id")
                    )
                    return f"""
                    {self.chat_styles}
                    <div>Thank you for your inquiry, {inquiry_data["name"]}! We've received your details and will get back to you soon.</div>
                    """
                return f"""
                {self.chat_styles}
                <div>Error processing your inquiry. Please ensure all fields are filled correctly.</div>
                """

            # Agent invocation
            try:
                response = await self.agent.ainvoke({"input": user_message})
                output = response["output"]
            except Exception as e:
                logger.error(f"Error in agent invocation: {e}")
                output = "I'm having trouble processing your request. Can you try asking about our services, job openings, or contact information?"

            # Service-related queries
            service_keywords = ["service", "services", "offering", "interested"]
            if any(keyword in user_message.lower() for keyword in service_keywords):
                services_tool = next((t for t in self.agent.tools.values() if t.name == "get_services_list"), None)
                if services_tool:
                    services = services_tool._run()
                    if services:
                        service_list_html = f"""
                        {self.chat_styles}
                        <div class="chat-container">
                            <div class="section-header">Services Offered by LogBinary</div>
                            <ul class="styled-list">
                        """
                        for service in services:
                            service_list_html += f"""
                                <li class="bullet-item">
                                    <span class="service-title">{service['name']}</span> - {service.get('category', 'Category not specified')}
                                    <div class="service-desc">{service.get('description', 'No description available')}</div>
                                </li>
                            """
                        service_list_html += f"""
                            </ul>
                            <p class="prompt-question">Interested in one of these services? Say 'apply' or 'yes' to proceed!</p>
                        </div>
                        """
                        self.context["last_topic"] = "service_list"
                        return service_list_html

            # Service inquiry form
            apply_keywords = ["apply", "yes"]
            if any(keyword in user_message.lower() for keyword in apply_keywords) and self.context.get("last_topic") == "service_list":
                services_tool = next((t for t in self.agent.tools.values() if t.name == "get_services_list"), None)
                services = services_tool._run() if services_tool else []
                return f"""
                {self.chat_styles}
                <div class="inquiry-form">
                    <p>Please provide your details to inquire about our services!</p>
                    <form id="inquiryForm">
                        <div class="form-group">
                            <label for="name">Your Name</label>
                            <input type="text" id="name" name="name" required>
                        </div>
                        <div class="form-group">
                            <label for="email">Business Email</label>
                            <input type="email" id="email" name="email" required>
                        </div>
                        <div class="form-group">
                            <label for="phone">Phone Number</label>
                            <input type="tel" id="phone" name="phone" required>
                        </div>
                        <div class="form-group">
                            <label for="subject">Subject</label>
                            <input type="text" id="subject" name="subject" required>
                        </div>
                        <div class="form-group">
                            <label for="message">Message</label>
                            <textarea id="message" name="message" rows="4" required></textarea>
                        </div>
                        <div class="form-group">
                            <input type="submit" value="Submit Inquiry">
                        </div>
                    </form>
                    <p>By submitting, you acknowledge LogBinary collects and handles your information as described in our <a href="#">Privacy Notice</a>.</p>
                </div>
                <script>
                document.getElementById('inquiryForm').addEventListener('submit', async function(e) {{
                    e.preventDefault();
                    const formData = new FormData(this);
                    const data = Object.fromEntries(formData);
                    await socket.send(JSON.stringify({{ 
                        action: 'submit_inquiry', 
                        data: {{
                            name: data.name,
                            email: data.email,
                            phone: data.phone,
                            subject: data.subject,
                            message: data.message,
                            service_id: '{services[0]['id'] if services else ''}'
                        }} 
                    }}));
                    this.reset();
                    return false;
                }});
                </script>
                """

            # Job-related logic (unchanged from your original)
            job_keywords = ["job", "career", "position", "opening", "employment"]
            apply_keywords = ["apply", "yes"]
            if any(keyword in user_message.lower() for keyword in job_keywords):
                jobs_tool = next((t for t in self.agent.tools.values() if t.name == "get_jobs_list"), None)
                if jobs_tool:
                    jobs = jobs_tool._run()
                    if jobs:
                        job_list_html = f"""
                        {self.chat_styles}
                        <div class="chat-container">
                            <div class="section-header">Current Job Openings at LogBinary</div>
                            <ul class="styled-list">
                        """
                        for job in jobs:
                            job_list_html += f"""
                                <li class="bullet-item">
                                    <span class="job-title">{job['title']}</span> - {job.get('location', 'Location not specified')}
                                    <div class="job-desc">{job.get('description', 'No description available')}</div>
                                </li>
                            """
                        job_list_html += f"""
                            </ul>
                            <p class="prompt-question">Would you like to apply for one of these positions? Please say 'apply' or 'yes'!</p>
                        </div>
                        """
                        self.context["last_topic"] = "job_list"
                        return job_list_html

            if any(keyword in user_message.lower() for keyword in apply_keywords) and self.context.get("last_topic") == "job_list":
                return f"""
                {self.chat_styles}
                <div class="inquiry-form">
                    <p>We're excited you're interested in joining LogBinary! Please complete the application below.</p>
                    <form id="jobApplicationForm" enctype="multipart/form-data">
                        <div class="form-group">
                            <label for="name">Full Name</label>
                            <input type="text" id="name" name="name" required>
                        </div>
                        <div class="form-group">
                            <label for="email">Email Address</label>
                            <input type="email" id="email" name="email" required>
                        </div>
                        <div class="form-group">
                            <label for="phone">Phone Number</label>
                            <input type="tel" id="phone" name="phone" required>
                        </div>
                        <div class="form-group">
                            <label for="resume">Resume (PDF or DOCX only)</label>
                            <input type="file" id="resume" name="resume" accept=".pdf,.docx" required>
                        </div>
                        <div class="form-group">
                            <input type="submit" value="Submit Application">
                        </div>
                    </form>
                    <p>By submitting, you acknowledge LogBinary collects and handles your information as described in our <a href="#">Privacy Notice</a>.</p>
                </div>
                <script>
                document.getElementById('jobApplicationForm').addEventListener('submit', async function(e) {{
                    e.preventDefault();
                    const formData = new FormData(this);
                    const data = Object.fromEntries(formData);
                    const resumeFile = document.getElementById('resume').files[0];
                    if (resumeFile) {{
                        data.resume_file = resumeFile.name;
                    }}
                    await socket.send(JSON.stringify({{ action: 'submit_job_application', data }}));
                    this.reset();
                    return false;
                }});
                </script>
                """
            # Add this code to your process_message method, alongside your other condition blocks

            contact_keywords = ["contact", "reach", "info", "phone", "email", "hours"]
            if any(keyword in user_message.lower() for keyword in contact_keywords):
                contact_tool = next((t for t in self.agent.tools.values() if t.name == "get_contact_info"), None)
                if contact_tool:
                    contact_info = contact_tool._run()
                    if contact_info:
                        contact_html = f"""
                        {self.chat_styles}
                        <div class="chat-container">
                            <div class="section-header">Here's how you can contact LogBinary</div>
                            <ul class="styled-list">
                        """
                        
                        # Add email if available
                        if "email" in contact_info:
                            contact_html += f"""
                                <li class="bullet-item">
                                    <span class="highlight">Email:</span> {contact_info["email"]}
                                </li>
                            """
                            
                        # Add phone numbers by region
                        for key in contact_info:
                            if key.startswith("phone_"):
                                region = key.replace("phone_", "").capitalize()
                                contact_html += f"""
                                    <li class="bullet-item">
                                        <span class="highlight">Phone ({region}):</span> {contact_info[key]}
                                    </li>
                                """
                            
                        # Add addresses by region
                        for key in contact_info:
                            if key.startswith("address_"):
                                region = key.replace("address_", "").capitalize()
                                contact_html += f"""
                                    <li class="bullet-item">
                                        <span class="highlight">Office ({region}):</span> {contact_info[key]}
                                    </li>
                                """
                        
                        contact_html += f"""
                            </ul>
                            <p>Feel free to reach out during business hours for any inquiries about our services or job opportunities.</p>
                        </div>
                        """
                        
                        self.context["last_topic"] = "contact_info"
                        return contact_html
            # Clean and return agent output for non-special cases
            output = self.clean_markdown(output)
            if "I'm LogBinary's virtual assistant" in output:
                output = self.chat_styles + output
            return output

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "Oops, something went wrong! How about asking me about our services, jobs, or contact info?"

    def clean_markdown(self, text):
        text = text.replace("**", "<strong>").replace("**", "</strong>")
        text = text.replace("*", "<em>").replace("*", "</em>")
        return text