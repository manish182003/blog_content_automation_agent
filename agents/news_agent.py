import json
import logging
import time
from typing import Dict, Any, List
import feedparser

import config
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# RSS feed endpoints
RSS_FEEDS = [
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "AI"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "AI"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "AI"},
    {"name": "Android Authority", "url": "https://www.androidauthority.com/feed/", "category": "Mobile App Development"},
    {"name": "Hacker News RSS", "url": "https://news.ycombinator.com/rss", "category": "AI"}
]

class TechNewsAgent(BaseAgent):
    """
    Agent 2: Tech News Agent
    Pulls recent AI and Mobile App Dev news via feedparser RSS feeds.
    Includes deduplication and fallback to cached news.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="TechNewsAgent", llm_client=llm_client)

    def _fetch_feed(self, feed_info: Dict[str, str]) -> List[Dict[str, Any]]:
        articles = []
        try:
            parsed = feedparser.parse(feed_info["url"])
            for entry in parsed.entries[:5]: # Top 5 per feed
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                link = entry.get("link", "")
                published = entry.get("published", entry.get("updated", ""))

                if title:
                    articles.append({
                        "title": title,
                        "summary": summary[:300] if summary else title,
                        "source": feed_info["name"],
                        "url": link,
                        "published": published,
                        "category": feed_info["category"]
                    })
        except Exception as e:
            logger.warning(f"Failed to fetch or parse RSS feed {feed_info['name']} ({feed_info['url']}): {e}")
        return articles

    def _load_cached_news(self) -> List[Dict[str, Any]]:
        """Load fallback cached news."""
        if config.CACHED_NEWS_PATH.exists():
            try:
                with open(config.CACHED_NEWS_PATH, "r", encoding="utf-8") as f:
                    logger.warning("Using cached tech news file as RSS feeds were unavailable.")
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read cached news file: {e}")
        return []

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 2: Tech News Agent...")
        all_articles = []
        seen_titles = set()

        for feed in RSS_FEEDS:
            items = self._fetch_feed(feed)
            for item in items:
                # Dedupe by title similarity / clean title
                clean_t = item["title"].lower()
                if clean_t not in seen_titles:
                    seen_titles.add(clean_t)
                    all_articles.append(item)

        # Fallback if no news fetched
        if not all_articles:
            logger.warning("All RSS feeds returned empty or failed. Loading cached news.")
            all_articles = self._load_cached_news()
        else:
            # Update cache file for future offline fallbacks
            try:
                with open(config.CACHED_NEWS_PATH, "w", encoding="utf-8") as f:
                    json.dump(all_articles[:15], f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to update news cache: {e}")

        logger.info(f"Agent 2 gathered {len(all_articles)} tech news articles.")
        return {"news_items": all_articles}
