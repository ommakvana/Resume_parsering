from typing import List, Dict, Optional
from groq import Groq
from config import GROQ_API_KEY, logger
import traceback

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

