from pydantic import BaseModel, Field
from typing import Optional

class ServiceInquiry(BaseModel):
    name: str = Field(description="Customer's full name")
    email: str = Field(description="Customer's email address")
    phone : str = Field(description="Customer's phone number")
    Subject: str = Field(description="Subject of Inquiry")
    Message: str = Field(description="Message to the Owner")

class JobApplication(BaseModel):
    name: str = Field(description="Applicant's full name")
    email: str = Field(description="Applicant's email address")
    job_id: str = Field(description="ID of the job")
    resume: str = Field(description="Upload a resume as a PDF or DocX file")
    cover_letter: Optional[str] = Field(default=None, description="Optional cover letter")