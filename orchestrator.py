import time
import logging
import uuid
from typing import Dict, Any, Optional

import config
from llm.client import GroqClientWrapper
from logger_metrics import MetricsLogger
from notifier import NotificationManager

from agents.keyword_agent import KeywordResearchAgent
from agents.news_agent import TechNewsAgent
from agents.past_blog_agent import PastBlogSummarizerAgent
from agents.topic_agent import TopicSelectionAgent
from agents.content_agent import ContentGenerationAgent
from agents.seo_agent import SEOValidatorAgent
from agents.groundedness_agent import GroundednessAuditorAgent
from agents.metadata_agent import MetadataAgent
from agents.publisher_agent import PublisherAgent

logger = logging.getLogger(__name__)

class BlogOrchestratorDAG:
    """
    DAG Orchestrator managing execution flow through all 9 autonomous agents.
    Includes feedback loops, rewrite limits, fallback handling, and reliability logging.
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.llm = GroqClientWrapper()
        self.logger_metrics = MetricsLogger()
        self.notifier = NotificationManager()

        # Initialize pipeline agents
        self.keyword_agent = KeywordResearchAgent(llm_client=self.llm)
        self.news_agent = TechNewsAgent(llm_client=self.llm)
        self.past_blog_agent = PastBlogSummarizerAgent(llm_client=self.llm)
        self.topic_agent = TopicSelectionAgent(llm_client=self.llm)
        self.content_agent = ContentGenerationAgent(llm_client=self.llm)
        self.seo_agent = SEOValidatorAgent(llm_client=self.llm)
        self.groundedness_agent = GroundednessAuditorAgent(llm_client=self.llm)
        self.metadata_agent = MetadataAgent(llm_client=self.llm)
        self.publisher_agent = PublisherAgent(llm_client=self.llm)

    def run_pipeline(self) -> Dict[str, Any]:
        """Execute the daily blog generation DAG pipeline."""
        start_time = time.time()
        run_id = f"run_{time.strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:6]}"
        mode_str = "DRY_RUN" if self.dry_run else "LIVE"

        logger.info(f"=== STARTING BLOG AUTOMATION PIPELINE [{run_id}] | Mode: {mode_str} ===")

        # Idempotency check for live publishing
        if not self.dry_run and self.logger_metrics.has_published_today():
            msg = "Idempotency check: A blog post has already been published to Notion today. Aborting run."
            logger.warning(msg)
            return {"status": "SKIPPED", "reason": msg}

        context: Dict[str, Any] = {
            "run_id": run_id,
            "dry_run": self.dry_run,
            "mode": mode_str,
            "agent_logs": {},
            "audit_feedback": None
        }

        rewrite_attempts = 0
        final_status = "FAILED"
        error_message = None

        try:
            # Step 1: Keyword Research Agent
            res_kw = self.keyword_agent.run(context)
            context.update(res_kw)
            context["agent_logs"]["keyword_agent"] = "SUCCESS"
            time.sleep(2)

            # Step 2: Tech News Agent
            res_news = self.news_agent.run(context)
            context.update(res_news)
            context["agent_logs"]["news_agent"] = "SUCCESS"
            time.sleep(2)

            # Step 3: Past-Blog Summarizer Agent
            res_past = self.past_blog_agent.run(context)
            context.update(res_past)
            context["agent_logs"]["past_blog_agent"] = "SUCCESS"
            time.sleep(2)

            # Step 4: Topic Selection Agent
            res_topic = self.topic_agent.run(context)
            context.update(res_topic)
            context["agent_logs"]["topic_agent"] = "SUCCESS"
            if res_topic.get("chosen_topic"):
                self.past_blog_agent.record_new_topic(res_topic["chosen_topic"])
            time.sleep(2)

            # Step 5-7: Content Generation & Audit Feedback Loop
            audit_passed = False
            
            while rewrite_attempts <= config.MAX_REWRITE_ATTEMPTS:
                logger.info(f"--- Content Generation Attempt {rewrite_attempts + 1}/{config.MAX_REWRITE_ATTEMPTS + 1} ---")
                
                # Step 5: Content Generation Agent
                res_content = self.content_agent.run(context)
                context.update(res_content)
                time.sleep(2)

                # Step 6: SEO Validator Agent
                res_seo = self.seo_agent.run(context)
                context.update(res_seo)
                time.sleep(2)

                # Step 7: Groundedness Auditor Agent
                res_ground = self.groundedness_agent.run(context)
                context.update(res_ground)
                time.sleep(2)

                # Evaluate audits
                if res_seo.get("seo_passed") and res_ground.get("groundedness_passed"):
                    audit_passed = True
                    logger.info("Quality and SEO Audits PASSED!")
                    break

                rewrite_attempts += 1
                if rewrite_attempts <= config.MAX_REWRITE_ATTEMPTS:
                    # Construct targeted rewrite feedback for next iteration
                    feedback_items = []
                    if not res_seo.get("seo_passed"):
                        feedback_items.extend(res_seo.get("seo_feedback", []))
                    if not res_ground.get("groundedness_passed"):
                        feedback_items.extend(res_ground.get("groundedness_feedback", []))

                    context["audit_feedback"] = "\n".join(f"- {item}" for item in feedback_items)
                    logger.warning(f"Audit failed. Looping back to Content Generation with feedback:\n{context['audit_feedback']}")

            if audit_passed:
                final_status = "SUCCESS"
            else:
                final_status = "NEEDS_REVIEW"
                logger.warning(f"Draft did not pass quality thresholds after {config.MAX_REWRITE_ATTEMPTS} attempts. Set to NEEDS_REVIEW.")

            # Step 8: Metadata Agent
            res_meta = self.metadata_agent.run(context)
            context.update(res_meta)
            context["agent_logs"]["metadata_agent"] = "SUCCESS"
            time.sleep(2)

            # Step 9: Publisher Agent
            res_pub = self.publisher_agent.run(context)
            context.update(res_pub)
            context["agent_logs"]["publisher_agent"] = "SUCCESS"

        except Exception as e:
            logger.error(f"Pipeline execution encountered an unhandled error: {e}", exc_info=True)
            final_status = "FAILED"
            error_message = str(e)

        duration = time.time() - start_time
        context["duration_seconds"] = duration
        context["rewrite_attempts"] = rewrite_attempts

        # Record metrics in SQLite
        self.logger_metrics.record_run(
            run_id=run_id,
            mode=mode_str,
            status=final_status,
            topic=context.get("chosen_topic"),
            category=context.get("category"),
            keyword=context.get("target_keyword"),
            seo_score=context.get("seo_overall_score"),
            groundedness_score=context.get("groundedness_overall_score"),
            rewrite_attempts=rewrite_attempts,
            duration_seconds=duration,
            agent_logs=context.get("agent_logs"),
            notion_page_id=context.get("notion_page_id"),
            error_message=error_message
        )

        # Dispatch end-of-run notifications
        self.notifier.send_notification(
            title=f"Blog Run [{run_id}]",
            details={
                "topic": context.get("chosen_topic"),
                "category": context.get("category"),
                "keyword": context.get("target_keyword"),
                "mode": mode_str,
                "seo_score": context.get("seo_overall_score"),
                "groundedness_score": context.get("groundedness_overall_score"),
                "duration_seconds": duration,
                "output_path": context.get("output_path"),
                "notion_url": context.get("notion_url"),
                "error_message": error_message
            },
            status=final_status
        )

        logger.info(f"=== COMPLETED BLOG PIPELINE [{run_id}] | Status: {final_status} | Duration: {duration:.1f}s ===")
        return context
