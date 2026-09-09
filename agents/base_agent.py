import logging
from typing import Dict, Any
from llm.client import GroqClientWrapper

logger = logging.getLogger(__name__)

class BaseAgent:
    """Abstract Base Agent class for the pipeline."""

    def __init__(self, name: str, llm_client: BaseAgent = None):
        self.name = name
        self.llm = llm_client or GroqClientWrapper()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's main task.
        Must accept shared context dict and return updated state updates.
        """
        raise NotImplementedError("Agents must implement run()")
