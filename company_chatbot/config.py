import os
import logging
from dotenv import load_dotenv
import csv

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