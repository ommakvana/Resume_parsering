"""Sequential Groq API client with key rotation."""

import os
import json
from groq import Groq
from data_ingestion.config import API_KEYS

class SequentialGroqClient:
    """A client that rotates through multiple Groq API keys."""

    def __init__(self, api_keys):
        """Initialize with a list of API keys."""
        self.api_keys = api_keys
        self.current_key_index = 0
        self.request_counts = {key: 0 for key in api_keys}
        self.max_requests_per_key = 1000
        self.load_counts()

    def load_counts(self):
        """Load request counts from file if available."""
        try:
            if os.path.exists('grok_work/api_request_counts.json'):
                with open('grok_work/api_request_counts.json', 'r') as f:
                    self.request_counts = json.load(f)
        except Exception as e:
            print(f"Error loading request counts: {e}")

    def save_counts(self):
        """Save request counts to file."""
        try:
            with open('grok_work/api_request_counts.json', 'w') as f:
                json.dump(self.request_counts, f)
        except Exception as e:
            print(f"Error saving request counts: {e}")

    def get_current_key(self):
        """Return the current API key."""
        return self.api_keys[self.current_key_index]

    def get_current_client(self):
        """Return a Groq client with the current API key."""
        os.environ["GROQ_API_KEY"] = self.get_current_key()
        return Groq()

    def move_to_next_key_if_needed(self):
        """Switch to the next key if the current one exceeds the limit."""
        current_key = self.get_current_key()
        if self.request_counts[current_key] >= self.max_requests_per_key:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            print(f"Switched to API key #{self.current_key_index + 1}")
            if all(self.request_counts[key] >= self.max_requests_per_key for key in self.api_keys):
                print("WARNING: All API keys have reached their daily limits!")

    def make_request(self, model, messages, temperature=0, max_completion_tokens=6790, top_p=0.95, stream=True):
        """Make a request to the Groq API with key rotation."""
        self.move_to_next_key_if_needed()
        current_key = self.get_current_key()
        client = self.get_current_client()

        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
                top_p=top_p,
                stream=stream
            )
            self.request_counts[current_key] += 1
            self.save_counts()
            return completion
        except Exception as e:
            print(f"Error with API key #{self.current_key_index + 1}: {e}")
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            return self.make_request(model, messages, temperature, max_completion_tokens, top_p, stream)


client = SequentialGroqClient(API_KEYS)