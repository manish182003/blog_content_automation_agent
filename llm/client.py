import json
import logging
import time
from typing import Dict, Any, List, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import config

logger = logging.getLogger(__name__)

class LLMClientError(Exception):
    """Custom exception for LLM API errors."""
    pass

class GroqClientWrapper:
    """Wrapper around Groq OpenAI-compatible chat completion endpoint."""

    def __init__(self, api_key: Optional[str] = None, primary_model: Optional[str] = None, fallback_model: Optional[str] = None):
        self.api_key = api_key or config.GROQ_API_KEY
        self.primary_model = primary_model or config.GROQ_MODEL
        self.fallback_model = fallback_model or config.GROQ_FALLBACK_MODEL
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def _make_request(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7, json_mode: bool = False) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutonomousBlogAgent/1.0"
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=45)
        
        if response.status_code != 200:
            logger.warning(f"Groq API call to {model} returned HTTP {response.status_code}: {response.text}")
            if response.status_code == 429:
                # Sleep briefly to respect Groq rate limits
                time.sleep(12)
            raise LLMClientError(f"HTTP {response.status_code}: {response.text}")

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMClientError(f"Unexpected response structure from Groq: {data}") from e

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        retry=retry_if_exception_type(LLMClientError),
        reraise=True
    )
    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7, json_mode: bool = False) -> str:
        """Execute LLM generation with primary model, retries, and fallback model."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Try primary model first
        try:
            return self._make_request(self.primary_model, messages, temperature=temperature, json_mode=json_mode)
        except LLMClientError as primary_err:
            logger.warning(f"Primary model ({self.primary_model}) failed: {primary_err}. Trying fallback ({self.fallback_model})...")
            # Try fallback model
            try:
                return self._make_request(self.fallback_model, messages, temperature=temperature, json_mode=json_mode)
            except LLMClientError as fallback_err:
                logger.error(f"Fallback model ({self.fallback_model}) also failed: {fallback_err}")
                raise fallback_err

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.3) -> Dict[str, Any]:
        """Convenience method to generate and parse structured JSON responses."""
        raw_res = self.generate(prompt=prompt, system_prompt=system_prompt, temperature=temperature, json_mode=True)
        try:
            return json.loads(raw_res)
        except json.JSONDecodeError as err:
            logger.error(f"Failed to parse JSON response from LLM: {raw_res}")
            # Clean markdown codeblocks if LLM returned ```json ... ```
            cleaned = raw_res.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            try:
                return json.loads(cleaned.strip())
            except json.JSONDecodeError:
                raise LLMClientError(f"Could not parse valid JSON from output: {raw_res}") from err
