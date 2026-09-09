import json
import logging
from typing import Dict, Any, List

import config
from agents.base_agent import BaseAgent
from utils_text import calculate_ngram_similarity

logger = logging.getLogger(__name__)

class GroundednessAuditorAgent(BaseAgent):
    """
    Agent 7: Quality / Groundedness Auditor Agent
    LLM-as-Judge check evaluating relevance, faithfulness, and factual groundedness,
    plus an n-gram plagiarism checker.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="GroundednessAuditorAgent", llm_client=llm_client)

    def _check_ngram_overlap(self, draft: str, news_items: List[Dict[str, Any]]) -> float:
        max_similarity = 0.0
        for item in news_items:
            source_text = f"{item.get('title', '')} {item.get('summary', '')}"
            sim = calculate_ngram_similarity(draft, source_text, n=4)
            if sim > max_similarity:
                max_similarity = sim
        return max_similarity

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 7: Quality / Groundedness Auditor Agent...")
        draft = context.get("draft_content", "")
        topic = context.get("chosen_topic", "")
        supporting_facts = context.get("supporting_facts", [])
        news_items = context.get("news_items", [])

        # Step 1: Plagiarism n-gram overlap check
        ngram_sim = self._check_ngram_overlap(draft, news_items)
        plagiarism_flag = ngram_sim > 0.35 # >35% 4-gram overlap flagged

        # Sample draft if extremely long to avoid Groq TPM limits
        eval_draft = draft
        if len(draft) > 6500:
            eval_draft = draft[:4000] + "\n\n... [MIDDLE SECTION WALKTHROUGH TRUNCATED FOR LLM AUDIT] ...\n\n" + draft[-2500:]

        # Step 2: LLM-as-Judge groundedness audit
        prompt = (
            f"You are a strict technical facts auditor evaluating a generated tech blog post.\n\n"
            f"Chosen Topic: '{topic}'\n\n"
            f"Source News Context & Facts:\n" + json.dumps(supporting_facts, indent=2) + "\n\n"
            f"Draft Content:\n"
            f"--- START DRAFT ---\n"
            f"{eval_draft}\n"
            f"--- END DRAFT ---\n\n"
            f"Evaluate the draft on three dimensions (0-100 each):\n"
            f"1. Relevance: Does the article stay on topic and address the target subject directly?\n"
            f"2. Faithfulness: Does it avoid contradicting the provided source news context?\n"
            f"3. Groundedness: Are specific claims, numbers, and news events grounded in reality rather than hallucinatory speculation?\n\n"
            f"Return a JSON object with fields:\n"
            f"- 'relevance_score': integer (0-100)\n"
            f"- 'faithfulness_score': integer (0-100)\n"
            f"- 'groundedness_score': integer (0-100)\n"
            f"- 'passed': boolean (true ONLY IF overall score >= {config.GROUNDEDNESS_PASS_THRESHOLD})\n"
            f"- 'itemized_feedback': list of strings detailing any ungrounded or hallucinated claims"
        )

        res = self.llm.generate_json(prompt, system_prompt="You are a meticulous technical editor and auditor.", temperature=0.1)

        rel = int(res.get("relevance_score", 0))
        faith = int(res.get("faithfulness_score", 0))
        ground = int(res.get("groundedness_score", 0))
        
        overall_score = round((rel + faith + ground) / 3.0, 1)

        feedback = res.get("itemized_feedback", [])
        if plagiarism_flag:
            feedback.append(f"High text overlap detected ({round(ngram_sim * 100, 1)}% 4-gram similarity). Paraphrase closely quoted sections.")

        passed = overall_score >= config.GROUNDEDNESS_PASS_THRESHOLD and not plagiarism_flag

        logger.info(
            f"Agent 7 Audit completed. Relevance: {rel}, Faithfulness: {faith}, Groundedness: {ground}. "
            f"Overall: {overall_score}/100. N-gram Sim: {round(ngram_sim*100, 1)}%. Passed: {passed}"
        )

        return {
            "groundedness_passed": passed,
            "relevance_score": rel,
            "faithfulness_score": faith,
            "groundedness_score": ground,
            "groundedness_overall_score": overall_score,
            "ngram_similarity": ngram_sim,
            "groundedness_feedback": feedback
        }
