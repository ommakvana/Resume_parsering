"""Simplified Groq API client for single API key usage."""

import os
from groq import Groq
# Load environment variables
from dotenv import load_dotenv
from config import logger

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not found in environment variables, using fallback method")
    GROQ_API_KEY = "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"

class GroqClient:
    """A simple client for making requests to the Groq API with a single key."""

    def __init__(self, api_key):
        """Initialize with a single API key."""
        self.api_key = api_key
        self.request_count = 0

    def get_client(self):
        """Return a Groq client with the API key."""
        os.environ["GROQ_API_KEY"] = self.api_key
        return Groq()

    def make_request(self, model, messages, temperature=0, max_completion_tokens=6790, top_p=0.95, stream=True):
        """Make a request to the Groq API."""
        client = self.get_client()

        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
                top_p=top_p,
                stream=stream
            )
            self.request_count += 1
            return completion
        except Exception as e:
            logger.error(f"Error with API request: {e}")
            raise

# Initialize the client with a single API key
client = GroqClient(GROQ_API_KEY)