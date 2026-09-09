import json
import logging
from typing import Dict, Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class MetadataAgent(BaseAgent):
    """
    Agent 8: Metadata Agent
    Generates SEO title, Meta Description, URL Slug, Excerpt, and Category metadata
    tailored for Notion page properties and site syndication.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="MetadataAgent", llm_client=llm_client)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 8: Metadata Agent...")
        topic = context.get("chosen_topic", "")
        keyword = context.get("target_keyword", "")
        category = context.get("category", "AI")
        draft = context.get("draft_content", "")

        prompt = (
            f"Generate metadata properties for a published blog post.\n\n"
            f"Topic: {topic}\n"
            f"Target Keyword: {keyword}\n"
            f"Category: {category}\n"
            f"Article Snippet: {draft[:500]}\n\n"
            f"Return a JSON object with properties:\n"
            f"- 'seo_title': string (under 60 chars, includes target keyword)\n"
            f"- 'meta_description': string (under 160 chars, enticing summary with target keyword)\n"
            f"- 'slug': string (lowercase, hyphen-separated URL slug, e.g. 'rag-vs-fine-tuning-flutter')\n"
            f"- 'excerpt': string (2-3 sentence overview)\n"
            f"- 'category': string (strictly 'AI' or 'Mobile App Development')\n"
        )

        res = self.llm.generate_json(prompt, system_prompt="You are an expert SEO metadata copywriter.", temperature=0.3)

        # Enforce valid category
        cat = res.get("category", category)
        if cat not in ["AI", "Mobile App Development"]:
            cat = category

        logger.info(f"Agent 8 generated metadata for slug: {res.get('slug')}")
        return {
            "metadata": {
                "seo_title": res.get("seo_title", topic),
                "meta_description": res.get("meta_description", topic),
                "slug": res.get("slug", topic.lower().replace(" ", "-")),
                "excerpt": res.get("excerpt", topic),
                "category": cat
            }
        }
