import json
import logging
import re
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

        if model.startswith("qwen"):
            payload["max_tokens"] = 900

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=45)
        
        if response.status_code != 200:
            logger.warning(f"Groq API call to {model} returned HTTP {response.status_code}: {response.text}")
            if response.status_code == 429:
                match = re.search(r'try again in ([0-9.]+)\s*s', response.text, re.IGNORECASE)
                if match:
                    wait_sec = float(match.group(1))
                    sleep_time = min(max(wait_sec + 1.0, 3.0), 45.0)
                    logger.info(f"Rate limited on {model}. Parsed retry wait time: {wait_sec}s. Sleeping for {sleep_time}s before retrying request...")
                    time.sleep(sleep_time)
                else:
                    time.sleep(8)
                
                # Retry in-flight request once after waiting
                response = requests.post(self.endpoint, headers=headers, json=payload, timeout=45)
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            
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
        """Execute LLM generation with multi-model fallback cascade."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build candidate model cascade
        candidate_models = []
        for m in [self.primary_model, self.fallback_model, "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
            if m and m not in candidate_models:
                candidate_models.append(m)

        last_error: Optional[LLMClientError] = None
        for model in candidate_models:
            try:
                return self._make_request(model, messages, temperature=temperature, json_mode=json_mode)
            except LLMClientError as err:
                last_error = err
                logger.warning(f"Model ({model}) failed: {err}. Trying next candidate model in cascade...")
                time.sleep(2)

        logger.error(f"All candidate models in cascade failed: {last_error}")
        if last_error is not None:
            raise last_error
        raise LLMClientError("All candidate models in cascade failed.")

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
