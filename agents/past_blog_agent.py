import json
import logging
from typing import Dict, Any, List
from notion_client import Client

import config
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

HISTORY_PATH = config.DATA_DIR / "history_topics.json"

class PastBlogSummarizerAgent(BaseAgent):
    """
    Agent 3: Past-Blog Summarizer Agent
    Queries existing posts from Notion database and local history JSON to extract
    previously covered topics, used keywords, and voice/style guidelines.
    Guarantees strict topic diversity.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="PastBlogSummarizerAgent", llm_client=llm_client)
        self.notion = Client(auth=config.NOTION_API_KEY) if config.NOTION_API_KEY else None

    def _query_notion_posts(self) -> List[Dict[str, Any]]:
        posts = []
        if not self.notion or not config.NOTION_DATABASE_ID:
            logger.warning("Notion API Key or Database ID not set. Skipping Notion query.")
            return posts

        try:
            res = self.notion.search(query="", filter={"property": "object", "value": "page"})
            for page in res.get("results", []):
                parent = page.get("parent", {})
                if parent.get("database_id", "").replace("-", "") == config.NOTION_DATABASE_ID.replace("-", ""):
                    props = page.get("properties", {})
                    
                    # Extract Title
                    title_objs = props.get("Title", {}).get("title", [])
                    title = title_objs[0]["text"]["content"] if title_objs else ""
                    
                    # Extract Category
                    cat_objs = props.get("Category", {}).get("rich_text", [])
                    category = cat_objs[0]["text"]["content"] if cat_objs else ""

                    # Extract Slug
                    slug_objs = props.get("Slug", {}).get("rich_text", [])
                    slug = slug_objs[0]["text"]["content"] if slug_objs else ""

                    if title:
                        posts.append({
                            "title": title,
                            "category": category,
                            "slug": slug
                        })
        except Exception as e:
            logger.warning(f"Notion database query failed: {e}. Proceeding with local history summary.")

        return posts

    def _load_local_history(self) -> List[str]:
        if HISTORY_PATH.exists():
            try:
                with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load local history topics: {e}")
        return []

    def record_new_topic(self, topic: str):
        """Record newly generated topic to local history JSON for future run exclusion."""
        history = self._load_local_history()
        if topic not in history:
            history.append(topic)
            try:
                with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                    json.dump(history[-30:], f, indent=2) # Keep last 30 topics
            except Exception as e:
                logger.warning(f"Failed to update local topic history: {e}")

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 3: Past-Blog Summarizer Agent...")
        past_posts = self._query_notion_posts()
        local_history = self._load_local_history()

        covered_topics = list(set([p["title"] for p in past_posts] + local_history))
        used_keywords = [p["slug"].replace("-", " ") for p in past_posts if p.get("slug")]

        # Build list of real internal links for authentic interlinking
        real_internal_links = [
            {
                "title": p["title"],
                "url": f"https://www.manishjoshi.online/blog/{p['slug']}"
            }
            for p in past_posts if p.get("slug")
        ]

        summary = {
            "post_count": len(past_posts),
            "covered_topics": covered_topics,
            "used_keywords": used_keywords,
            "voice_notes": "Conversational, practical, coffee-chat style with natural CTA for AI and Flutter app development work."
        }

        logger.info(f"Agent 3 retrieved {len(covered_topics)} past topics and {len(real_internal_links)} real internal links.")
        return {
            "past_blog_summary": summary,
            "used_keywords": used_keywords,
            "covered_topics": covered_topics,
            "real_internal_links": real_internal_links
        }
