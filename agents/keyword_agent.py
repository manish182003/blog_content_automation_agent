import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class KeywordResearchAgent(BaseAgent):
    """
    Agent 1: Keyword Research Agent
    Finds keyword candidates in AI or Mobile App Development using Google Autocomplete & Trends,
    with fallback to static seed keywords.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="KeywordResearchAgent", llm_client=llm_client)

    def _fetch_autocomplete_suggestions(self, seed_query: str) -> List[str]:
        """Fetch Google Search Autocomplete suggestions (free, no API key)."""
        try:
            url = f"https://suggestqueries.google.com/complete/search?client=chrome&q={urllib.parse.quote(seed_query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                if len(data) >= 2:
                    return data[1][:5]
        except Exception as e:
            logger.warning(f"Autocomplete fetch failed for '{seed_query}': {e}")
        return []

    def _fetch_pytrends_interest(self, keywords: List[str]) -> Dict[str, int]:
        """Fetch Google Trends interest via pytrends if available."""
        scores = {}
        try:
            from pytrends.request import TrendReq
            pytrend = TrendReq(hl='en-US', tz=360, timeout=(5, 10))
            # Test pytrends with small kw_list batch
            batch = keywords[:5]
            pytrend.build_payload(batch, cat=0, timeframe='now 7-d', geo='', gprop='')
            df = pytrend.interest_over_time()
            if not df.empty:
                for kw in batch:
                    if kw in df.columns:
                        scores[kw] = int(df[kw].mean())
        except Exception as e:
            logger.warning(f"PyTrends interest lookup failed: {e}")
        return scores

    def _load_fallback_keywords(self) -> List[Dict[str, Any]]:
        """Load seed fallback keywords from JSON."""
        if config.SEED_KEYWORDS_PATH.exists():
            try:
                with open(config.SEED_KEYWORDS_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read seed keywords file: {e}")
        return [
            {
                "keyword": "RAG vs Fine-Tuning for Mobile Apps",
                "category": "AI",
                "difficulty": "low",
                "interest_score": 85,
                "rationale": "High developer search volume for personalizing edge AI."
            },
            {
                "keyword": "Building Offline AI Features with Flutter",
                "category": "Mobile App Development",
                "difficulty": "low",
                "interest_score": 80,
                "rationale": "Growing demand for on-device small language models."
            }
        ]

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 1: Keyword Research Agent...")
        used_keywords = context.get("used_keywords", [])
        
        candidates = []
        seed_topics = ["Flutter AI integration", "Small language models mobile", "On-device LLM Android iOS"]

        try:
            expanded_queries = []
            for seed in seed_topics:
                suggestions = self._fetch_autocomplete_suggestions(seed)
                expanded_queries.extend(suggestions)

            if expanded_queries:
                trend_scores = self._fetch_pytrends_interest(expanded_queries[:5])
                
                # Rank candidates using LLM
                prompt = (
                    f"Evaluate the following tech search queries and select 3-5 top low-competition, "
                    f"high-interest keywords strictly categorized under 'AI' or 'Mobile App Development'.\n\n"
                    f"Queries: {json.dumps(expanded_queries)}\n"
                    f"Trend Scores: {json.dumps(trend_scores)}\n"
                    f"Recently used keywords to exclude: {json.dumps(used_keywords)}\n\n"
                    f"Return a JSON object with key 'candidates' containing a list of objects with fields:\n"
                    f"- 'keyword': string\n"
                    f"- 'category': string (strictly 'AI' or 'Mobile App Development')\n"
                    f"- 'difficulty': 'low' or 'medium'\n"
                    f"- 'interest_score': integer (0-100)\n"
                    f"- 'rationale': string short explanation"
                )
                
                res = self.llm.generate_json(prompt, system_prompt="You are a senior SEO keyword researcher for AI and Mobile App Development.")
                candidates = res.get("candidates", [])

        except Exception as e:
            logger.warning(f"Dynamic keyword research encountered an error: {e}. Falling back to static seed file.")

        if not candidates:
            # Fallback to seed keywords
            seed_data = self._load_fallback_keywords()
            # Filter out recently used
            candidates = [k for k in seed_data if k.get("keyword") not in used_keywords]
            if not candidates:
                candidates = seed_data

        logger.info(f"Agent 1 selected {len(candidates)} keyword candidates.")
        return {"keyword_candidates": candidates}
