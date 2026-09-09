import json
import logging
from typing import Dict, Any

import config
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class SEOValidatorAgent(BaseAgent):
    """
    Agent 6: SEO Validator Agent
    Evaluates classic Google SEO and Generative Engine Optimization (GEO/AI-search readiness).
    Assigns numerical scores (0-100) and itemized feedback.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="SEOValidatorAgent", llm_client=llm_client)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 6: SEO Validator Agent...")
        draft = context.get("draft_content", "")
        keyword = context.get("target_keyword", "")

        # Sample draft if extremely long to avoid Groq TPM limits
        eval_draft = draft
        if len(draft) > 6500:
            eval_draft = draft[:4000] + "\n\n... [MIDDLE SECTION WALKTHROUGH TRUNCATED FOR LLM AUDIT] ...\n\n" + draft[-2500:]

        prompt = (
            f"You are an expert SEO and AI-Search (GEO) Optimization Auditor.\n\n"
            f"Target Keyword: '{keyword}'\n\n"
            f"Draft Blog Post:\n"
            f"--- START DRAFT ---\n"
            f"{eval_draft}\n"
            f"--- END DRAFT ---\n\n"
            f"Audit Criteria:\n"
            f"1. Classic Google SEO Score (0-100):\n"
            f"   - Presence of keyword '{keyword}' in main title/H1, early H2, and within first 100 words.\n"
            f"   - Proper Markdown header hierarchy (H1 -> H2 -> H3).\n"
            f"   - Appropriate article length and scannable paragraph structure.\n"
            f"2. Generative Engine Optimization (GEO) / AI-Search Score (0-100):\n"
            f"   - Direct answer summary near the top of the post.\n"
            f"   - Clear, question/answer heading labels.\n"
            f"   - Scannable lists, code samples, or bullet points.\n\n"
            f"Return a JSON object with fields:\n"
            f"- 'google_seo_score': integer (0-100)\n"
            f"- 'geo_ai_search_score': integer (0-100)\n"
            f"- 'passed': boolean (true ONLY IF BOTH scores are >= {config.SEO_PASS_THRESHOLD})\n"
            f"- 'itemized_feedback': list of strings with specific action items for missing SEO elements"
        )

        res = self.llm.generate_json(prompt, system_prompt="You are a strict technical SEO validator.", temperature=0.2)

        google_score = int(res.get("google_seo_score", 0))
        geo_score = int(res.get("geo_ai_search_score", 0))
        passed = google_score >= config.SEO_PASS_THRESHOLD and geo_score >= config.SEO_PASS_THRESHOLD
        feedback = res.get("itemized_feedback", [])

        overall_score = round((google_score + geo_score) / 2.0, 1)

        logger.info(
            f"Agent 6 SEO Audit completed. Google SEO: {google_score}/100, GEO AI-Search: {geo_score}/100. "
            f"Passed: {passed}"
        )

        return {
            "seo_passed": passed,
            "google_seo_score": google_score,
            "geo_ai_search_score": geo_score,
            "seo_overall_score": overall_score,
            "seo_feedback": feedback
        }
