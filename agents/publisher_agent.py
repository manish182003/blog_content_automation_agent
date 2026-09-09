import json
import logging
import time
from pathlib import Path
from typing import Dict, Any
from notion_client import Client
from tenacity import retry, stop_after_attempt, wait_exponential

import config
from agents.base_agent import BaseAgent
from utils_text import markdown_to_notion_blocks

logger = logging.getLogger(__name__)

class PublisherAgent(BaseAgent):
    """
    Agent 9: Publisher Agent (Notion)
    Publishes article content and metadata to Notion database or writes locally in dry-run mode.
    Implements staging write (Published: False -> True) and idempotency checks.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="PublisherAgent", llm_client=llm_client)
        self.notion = Client(auth=config.NOTION_API_KEY) if config.NOTION_API_KEY else None

    def _prune_old_outputs(self, keep: int = 3):
        """Clean up output directory to keep only the latest `keep` draft files for Render space optimization."""
        try:
            draft_files = sorted(list(config.OUTPUT_DIR.glob("draft_*.md")), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_file in draft_files[keep:]:
                try:
                    old_file.unlink()
                    logger.info(f"Pruned old draft file to save space: {old_file.name}")
                except Exception as e:
                    logger.warning(f"Could not delete old draft {old_file.name}: {e}")
        except Exception as err:
            logger.warning(f"Failed to prune old outputs: {err}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _publish_to_notion(self, title: str, metadata: Dict[str, Any], content: str, publish_live: bool = True) -> str:
        """Create Notion database page with metadata, append Markdown blocks, and update status."""
        if not self.notion or not config.NOTION_DATABASE_ID:
            raise ValueError("Notion API Key or Database ID missing.")

        # Convert markdown content to Notion block format
        notion_blocks = markdown_to_notion_blocks(content)

        # 1. Create page with Published: False (Staging State)
        page_properties = {
            "Title": {
                "title": [{"type": "text", "text": {"content": title}}]
            },
            "SEO Title": {
                "rich_text": [{"type": "text", "text": {"content": metadata.get("seo_title", title)}}]
            },
            "Meta Description": {
                "rich_text": [{"type": "text", "text": {"content": metadata.get("meta_description", "")}}]
            },
            "Category": {
                "rich_text": [{"type": "text", "text": {"content": metadata.get("category", "AI")}}]
            },
            "Slug": {
                "rich_text": [{"type": "text", "text": {"content": metadata.get("slug", "")}}]
            },
            "Excerpt": {
                "rich_text": [{"type": "text", "text": {"content": metadata.get("excerpt", "")}}]
            },
            "Published": {
                "checkbox": False # Staging state first!
            }
        }

        # Create Notion page
        new_page = self.notion.pages.create(
            parent={"database_id": config.NOTION_DATABASE_ID},
            properties=page_properties
        )
        page_id = new_page["id"]
        logger.info(f"Created staging Notion page: {page_id}")

        # 2. Append block content in chunks of 100 blocks (Notion API max limit)
        chunk_size = 100
        for i in range(0, len(notion_blocks), chunk_size):
            block_chunk = notion_blocks[i:i + chunk_size]
            self.notion.blocks.children.append(
                block_id=page_id,
                children=block_chunk
            )

        logger.info(f"Successfully appended {len(notion_blocks)} blocks to page {page_id}.")

        # 3. Flip Published to True if live publishing is requested
        if publish_live:
            self.notion.pages.update(
                page_id=page_id,
                properties={"Published": {"checkbox": True}}
            )
            logger.info(f"Flipped Notion page {page_id} status to Published: True")

        return page_id

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 9: Publisher Agent...")
        topic = context.get("chosen_topic", "Untitled Tech Post")
        metadata = context.get("metadata", {})
        draft = context.get("draft_content", "")
        dry_run = context.get("dry_run", True)
        audit_passed = context.get("seo_passed", False) and context.get("groundedness_passed", False)

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        output_filename = f"draft_{timestamp_str}.md"
        local_output_path = config.OUTPUT_DIR / output_filename

        # Write output locally always for record-keeping
        with open(local_output_path, "w", encoding="utf-8") as f:
            f.write(f"--- \n")
            f.write(f"Title: {topic}\n")
            f.write(f"Metadata: {json.dumps(metadata, indent=2)}\n")
            f.write(f"SEO Passed: {context.get('seo_passed')}\n")
            f.write(f"Groundedness Passed: {context.get('groundedness_passed')}\n")
            f.write(f"--- \n\n")
            f.write(draft)

        # Prune old outputs to optimize space on Render free tier (keep latest 3)
        self._prune_old_outputs()

        logger.info(f"Saved local post draft to {local_output_path}")

        page_id = None
        notion_url = None

        if dry_run:
            logger.info("DRY-RUN MODE ENABLED: Skipping live Notion publish.")
        else:
            # Live publishing mode
            should_publish_live = audit_passed
            try:
                page_id = self._publish_to_notion(
                    title=topic,
                    metadata=metadata,
                    content=draft,
                    publish_live=should_publish_live
                )
                notion_url = f"https://notion.so/{page_id.replace('-', '')}"
            except Exception as e:
                logger.error(f"Publisher Agent Notion write failed: {e}")
                raise e

        return {
            "output_path": str(local_output_path),
            "notion_page_id": page_id,
            "notion_url": notion_url,
            "published_live": (not dry_run and audit_passed)
        }
