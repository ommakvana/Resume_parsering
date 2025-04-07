from typing import Dict, List, Any, Optional
import csv
from datetime import datetime
from config import COMPANY_CONFIG, JOB_OPPORTUNITIES, logger
from models import ServiceInquiry, JobApplication
import os
import logging

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

    def _run(self, name: str, email: str, phone: str, subject: str, message: str,service_id: Optional[str] = None) -> Dict:
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
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    description = "Submit a job application from a potential candidate and save contact details and resume."
    
    def _run(self, name: str, email: str, phone: str, resume_file: str) -> Dict:
        # Validate the resume file format
        if not (resume_file.lower().endswith('.pdf') or resume_file.lower().endswith('.docx')):
            return {"error": "Resume must be in PDF or DOCX format."}
        
        # Save to CSV
        csv_file = "job_applications.csv"
        fieldnames = ["name", "email", "phone", "resume_file", "timestamp"]
        
        application_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "resume_file": resume_file,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        file_exists = os.path.exists(csv_file)
        with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(application_data)
        
        logger.info(f"Job application submitted: {name}, {email}, {phone}, {resume_file}")
        return {
            "status": "success",
            "name": name,
            "email": email,
            "phone": phone,
            "message": "Your application has been successfully submitted."
        }

class GetContactInfoTool(BaseTool):
    name = "get_contact_info"
    description = "Retrieve the contact information for LogBinary as raw data or find specific contact details."
    
    def _run(self, query: Optional[str] = None) -> Dict:
        contact_info = COMPANY_CONFIG["contact_info"]
        
        # If a specific query is provided, try to return only the relevant information
        if query:
            query = query.lower()
            filtered_results = {}
            
            for key, value in contact_info.items():
                if query in key.lower():
                    filtered_results[key] = value
            
            return filtered_results if filtered_results else contact_info
            
        # Return all contact information if no specific query
        return contact_info