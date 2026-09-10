import json
import logging
from typing import Dict, Any, List

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class TopicSelectionAgent(BaseAgent):
    """
    Agent 4: Topic Selection Agent
    Selects exactly ONE tech topic (strictly AI or Mobile App Development) by combining
    keyword candidates, tech news context, and past blog history.
    Enforces strict topic diversity and category rotation.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="TopicSelectionAgent", llm_client=llm_client)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 4: Topic Selection Agent...")
        keyword_candidates = context.get("keyword_candidates", [])
        news_items = context.get("news_items", [])
        past_summary = context.get("past_blog_summary", {})
        covered_topics = context.get("covered_topics", [])

        # Determine last categories & banned subjects from covered topics
        recent_text = " ".join(covered_topics).lower()
        
        banned_concepts = []
        if "device" in recent_text or "quantization" in recent_text or "small language" in recent_text:
            banned_concepts.append("On-Device LLMs / Small Language Model Quantization")
        if "flutter" in recent_text:
            banned_concepts.append("Basic Flutter Setup")

        # Rotate strictly across 4 distinct domains
        last_category = "Mobile App Development"
        if covered_topics and len(covered_topics) > 0:
            last_title = covered_topics[-1].lower()
            if "flutter" in last_title or "mobile" in last_title:
                last_category = "Mobile App Development"
            elif "fastapi" in last_title or "node" in last_title or "backend" in last_title or "sql" in last_title or "redis" in last_title:
                last_category = "Backend Systems"
            elif "math" in last_title or "linear algebra" in last_title or "attention" in last_title or "gradient" in last_title:
                last_category = "AI Mathematics & CS Foundations"
            else:
                last_category = "AI & Agentic Systems"

        if last_category == "Mobile App Development":
            target_category = "Backend Systems"
        elif last_category == "Backend Systems":
            target_category = "AI Mathematics & CS Foundations"
        elif last_category == "AI Mathematics & CS Foundations":
            target_category = "AI & Agentic Systems"
        else:
            target_category = "Mobile App Development"

        banned_str = "\n".join(f"- STRICTLY BANNED TODAY: {concept}" for concept in banned_concepts) if banned_concepts else "None"

        prompt = (
            f"You are a senior technical editorial strategist for a high-traffic engineering blog.\n\n"
            f"STRICT DIVERSITY REQUIREMENT: Select a COMPLETELY NEW, UNIQUE tech topic.\n"
            f"Do NOT repeat or closely match any of these previously covered topics:\n"
            f"{json.dumps(covered_topics, indent=2)}\n\n"
            f"{banned_str}\n\n"
            f"Target Category Preference for Rotation Today: '{target_category}'\n"
            f"Allowed Categories: 'Backend Systems', 'AI Mathematics & CS Foundations', 'AI & Agentic Systems', 'Mobile App Development'.\n\n"
            f"Keyword Candidates:\n{json.dumps(keyword_candidates, indent=2)}\n\n"
            f"Recent Tech News Items:\n{json.dumps(news_items[:10], indent=2)}\n\n"
            f"Broad Topic Ideas Matrix across 8 engineering domains to ensure maximum variety:\n"
            f"1. Backend Systems: FastAPI vs Node.js for High-Throughput Async Microservices, Redis BullMQ Task Queues, PostgreSQL Query & Indexing Optimization.\n"
            f"2. Agentic AI: Building Stateful Multi-Agent Workflows with LangGraph, Tool Calling & Human-in-the-Loop Safeguards.\n"
            f"3. AI Mathematics: The Linear Algebra of Transformer Self-Attention (QKV Projections), Gradient Descent Optimization Math.\n"
            f"4. Machine Learning & Deep Learning: Model Distillation (Teacher to Student), Hyperparameter Tuning with Optuna, Vision Transformers vs CNNs.\n"
            f"5. Mobile Engineering: Flutter State Management (Riverpod vs Bloc), Optimizing Mobile App FPS & Rendering Bottlenecks, Offline SQLite Sync.\n"
            f"6. Vector Search: PostgreSQL pgvector vs Qdrant vs Chroma for Enterprise RAG Systems.\n"
            f"7. Reinforcement Learning: RLHF (PPO Fine-Tuning) and Deep Q-Learning decision systems.\n"
            f"8. Infrastructure & Cloud: Cloud Run Docker Deployments, Serverless Async Workers.\n\n"
            f"Return a JSON object with fields:\n"
            f"- 'chosen_topic': string (compelling, unique, highly technical article title)\n"
            f"- 'target_keyword': string (primary high-intent SEO keyword)\n"
            f"- 'category': string (one of the 4 allowed categories)\n"
            f"- 'angle': string (unique perspective or technical angle)\n"
            f"- 'selection_rationale': string (why this topic is unique and diverse compared to past posts)\n"
            f"- 'supporting_facts': array of strings (3 to 5 concrete facts or news links from the recent news context)\n"
        )

        res = self.llm.generate_json(prompt, system_prompt="You are a senior tech editor enforcing topic variety and technical depth.", temperature=0.8)
        
        # Ensure category fallback guardrail
        cat = res.get("category", target_category)
        if cat not in ["Backend Systems", "AI Mathematics & CS Foundations", "AI & Agentic Systems", "Mobile App Development"]:
            cat = target_category

        logger.info(f"Agent 4 selected topic: '{res.get('chosen_topic')}' [Category: {cat}]")
        return {
            "chosen_topic": res.get("chosen_topic"),
            "target_keyword": res.get("target_keyword"),
            "category": cat,
            "angle": res.get("angle"),
            "supporting_facts": res.get("supporting_facts", []),
            "selection_rationale": res.get("selection_rationale")
        }
