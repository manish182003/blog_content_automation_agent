from typing import List
import logging
import re
from typing import Dict, Any, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

MANDATORY_CTA = """
---

## 🚀 Ready to Build Your Next AI, Mobile, or Backend Product?

Whether you are looking to build a high-performance **Flutter mobile app**, an autonomous **Agentic AI workflow**, or a scalable **FastAPI / Node.js backend microservice**, I help founders and engineering teams turn ambitious ideas into production-ready software.

👉 **[Contact Manish Joshi](https://www.manishjoshi.online/contact)** to discuss your project requirements and start building your breakthrough product today.
"""

STYLE_DIRECTIVE = r"""
Write like a knowledgeable senior engineer explaining technical systems to a developer friend over coffee.
- Comprehensive technical depth: Target ~1800 to 2500 words across all sections. Provide real implementation details, not high-level summaries.
- Mostly short-to-medium sentences, under ~20 words.
- Contractions are fine (it's, don't, that's).
- No filler openers like "In today's fast-paced digital world" or "In this post, we'll explore."
- Avoid AI-cliché words/phrases: delve, tapestry, landscape, unlock, harness, game-changer, elevate, moreover, furthermore, it's important to note, unleash, in conclusion.
- Get to the point in the first two sentences.
- Use concrete code examples over abstract claims.
- Vary paragraph rhythm — don't make every paragraph the same shape or length.
- Headers should read like real questions or real answers, not vague labels.
- One idea per paragraph, 2–4 sentences.
- Include structured Markdown tables for benchmark metrics, trade-offs, and architecture comparisons.

CRITICAL CODE BLOCK & FORMATTING RULES:
- DO NOT write inline bash heredoc scripts (e.g. do NOT write `python - <<EOF ... EOF`).
- All code snippets MUST be inside standard multi-line markdown fenced code blocks with valid language tags (e.g. ```dart, ```swift, ```kotlin, ```python, ```typescript, ```bash, ```sql).
- Code blocks MUST be properly formatted with line breaks, proper indentation, and multi-line clean code syntax.
- DO NOT include HTML comments (`<!-- ... -->`).
- DO NOT include metadata header blocks (`Title:`, `Metadata:`, `SEO Passed:`). Output ONLY clean Markdown content.
- DO NOT cut off code snippets or paragraphs mid-sentence.

CRITICAL LINK & EMAIL RULES (NO HALLUCINATIONS):
- DO NOT invent, fabricate, or write fake internal links (e.g. DO NOT write "💡 Internal link: ..." or link to non-existent articles).
- DO NOT invent fake email addresses (e.g. DO NOT write "manish@ai-labs.dev").
- The ONLY allowed URL in the entire article is the official contact link: https://www.manishjoshi.online/contact.

CRITICAL MATH & EQUATION RULES:
- DO NOT use isolated floating square brackets '[' or ']' on separate lines for display math formulas.
- Write equations using clean, human-readable math notation (e.g. `A = softmax(QKᵀ / √d_k)`) or clean inline code. Avoid outputting raw unparsed LaTeX macros like `\text{softmax}!`, `\frac{...}{...}`, `\left(`, `\right)`.
"""

class ContentGenerationAgent(BaseAgent):
    """
    Agent 5: Content Generation Agent
    Generates rich, comprehensive technical blog posts (1800-2500 words) using a 2-Pass multi-chunk
    generation engine with completion guardrails and a mandatory conversion CTA.
    """

    def __init__(self, llm_client=None):
        super().__init__(name="ContentGenerationAgent", llm_client=llm_client)

    def _clean_math_notation(self, content: str) -> str:
        """Clean up broken LaTeX display math brackets, stray exclamation points, and raw LaTeX macros into clean readable math."""
        # 1. Remove isolated '[' and ']' lines surrounding formulas
        content = re.sub(r'(?m)^\s*\[\s*$\n?', '', content)
        content = re.sub(r'(?m)^\s*\]\s*$\n?', '', content)

        # 2. Clean raw LaTeX math macros into readable text symbols
        content = re.sub(r'\\text\{([^}]+)\}!?', r'\1', content)
        content = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1 / \2)', content)
        content = re.sub(r'\\sqrt\{([^}]+)\}', r'√\1', content)
        content = re.sub(r'\\left\(', '(', content)
        content = re.sub(r'\\right\)', ')', content)
        content = re.sub(r'\^\\top', 'ᵀ', content)
        return content

    def _clean_hallucinated_links(self, content: str, valid_urls: Optional[List[str]] = None) -> str:
        """Strip hallucinated internal link callouts, fake markdown links to non-existent posts, and fake emails while preserving real valid internal links."""
        content = self._clean_math_notation(content)
        valid_set = set(valid_urls or [])
        valid_set.add("https://www.manishjoshi.online/contact")

        # 1. Remove "💡 Internal link: ..." or "Internal link: ..." lines if they point to non-existent URLs
        # 2. Replace fake email addresses (e.g. manish@ai-labs.dev) with official contact link
        content = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'https://www.manishjoshi.online/contact', content)
        
        # 3. Clean any markdown links [Post Title](...) EXCEPT those matching valid_set
        def replace_link(match):
            text = match.group(1)
            url = match.group(2).strip()
            
            # Allow valid internal URLs or official contact link
            if url in valid_set or any(v in url for v in valid_set):
                return match.group(0)
            
            # If link is fake/hallucinated, convert to plain bold text
            return f"**{text}**"

        content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, content)
        return content

    def _ensure_complete_code_blocks(self, content: str) -> str:
        """Fix any unclosed code blocks by appending missing closing backticks."""
        backtick_count = len(re.findall(r'```', content))
        if backtick_count % 2 != 0:
            logger.warning("Detected unclosed code block in generated content; fixing automatically.")
            content = content.rstrip() + "\n```\n"
        return content

    def _ensure_cta_included(self, content: str) -> str:
        """Ensure the mandatory conversion CTA is present at the end of the post."""
        if "manishjoshi.online/contact" not in content.lower():
            logger.info("Appending mandatory conversion CTA to article end.")
            content = content.rstrip() + "\n\n" + MANDATORY_CTA.strip() + "\n"
        return content

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Executing Agent 5: Multi-Pass Content Generation Agent...")
        topic = context.get("chosen_topic", "Building Modern AI & Mobile Applications")
        keyword = context.get("target_keyword", "")
        category = context.get("category", "AI & Agentic Systems")
        angle = context.get("angle", "")
        supporting_facts = context.get("supporting_facts", [])
        feedback = context.get("audit_feedback")

        feedback_prompt = ""
        if feedback:
            logger.info(f"Incorporating rewrite audit feedback into Content Agent prompt:\n{feedback}")
            feedback_prompt = f"\nCRITICAL REWRITE AUDIT FEEDBACK (Must address all itemized points below):\n{feedback}\n"

        # PASS 1: Part A (Title, Direct Answer, Problem Statement, System Architecture, & Metric Table)
        prompt_part_a = (
            f"Write PART 1 of an in-depth technical guide (approx 700-900 words) in Markdown format for the topic below.\n\n"
            f"Topic: {topic}\n"
            f"Target Keyword: {keyword}\n"
            f"Category: {category}\n"
            f"Angle: {angle}\n"
            f"Supporting Context:\n" + "\n".join(f"- {fact}" for fact in supporting_facts) + "\n\n"
            f"Include the following sections in PART 1:\n"
            f"1. Main H1 Title: Ensure exact keyword '{keyword}' appears in the title.\n"
            f"2. Direct-Answer Summary: 1-2 sentences right after H1 directly answering the query for GEO AI-search.\n"
            f"3. Introduction & Real-World Engineering Context (~200 words, keyword in first 100 words).\n"
            f"4. H2: Problem Statement & System Architecture: Detailed breakdown of the technical problem.\n"
            f"5. Include a structured Markdown Table comparing architecture patterns or performance metrics.\n"
            f"{feedback_prompt}\n"
            f"Output ONLY clean Markdown for PART 1."
        )

        logger.info("Generating Part 1 (Intro, Architecture, Metrics Table)...")
        part_a = self.llm.generate(prompt=prompt_part_a, system_prompt=STYLE_DIRECTIVE, temperature=0.7)
        part_a = self._ensure_complete_code_blocks(part_a)

        # PASS 2: Part B (Step-by-Step Code Implementation & Walkthrough)
        prompt_part_b = (
            f"Write PART 2 of the technical guide (approx 800-1000 words) continuing directly from Part 1.\n\n"
            f"Topic: {topic}\n"
            f"Target Keyword: {keyword}\n"
            f"Category: {category}\n"
            f"Part 1 Context Summary:\n{part_a[:400]}...\n\n"
            f"Include the following sections in PART 2:\n"
            f"1. H2: Step-by-Step Implementation Guide with H3 sub-headings for each step.\n"
            f"2. Provide complete, realistic, multi-line code blocks with full logic in relevant languages (Dart/Flutter, Python/FastAPI, TypeScript/Node.js, or SQL).\n"
            f"3. Explain key lines, architectural decisions, and error-handling strategies after each code snippet.\n"
            f"4. Focus on deep implementation details that engineers can copy-paste and adapt.\n"
            f"Output ONLY clean Markdown for PART 2."
        )

        logger.info("Generating Part 2 (Step-by-Step Implementation & Code)...")
        part_b = self.llm.generate(prompt=prompt_part_b, system_prompt=STYLE_DIRECTIVE, temperature=0.7)
        part_b = self._ensure_complete_code_blocks(part_b)

        # PASS 3: Part C (Production Pitfalls, GEO FAQ, Conclusion & Client Conversion CTA)
        prompt_part_c = (
            f"Write PART 3 of the technical guide (approx 600-800 words) concluding the article.\n\n"
            f"Topic: {topic}\n"
            f"Target Keyword: {keyword}\n"
            f"Include the following sections in PART 3:\n"
            f"1. H2: Production Pitfalls & Performance Optimization (edge cases, memory leaks, concurrency, rate limits).\n"
            f"2. H2: Frequently Asked Questions (GEO AI-Search Q&A with 3 crisp Q&A subheadings).\n"
            f"3. H2: Final Summary & Key Takeaways.\n"
            f"4. Mandatory Client Conversion CTA: Highlighting Manish Joshi's expertise in Flutter, AI, Agentic Workflows, and FastAPI/Node.js backend engineering.\n"
            f"Output ONLY clean Markdown for PART 3."
        )

        logger.info("Generating Part 3 (Production Pitfalls, GEO FAQ, CTA)...")
        part_c = self.llm.generate(prompt=prompt_part_c, system_prompt=STYLE_DIRECTIVE, temperature=0.7)
        part_c = self._ensure_complete_code_blocks(part_c)

        # Stitch Parts together seamlessly
        full_draft = f"{part_a.strip()}\n\n{part_b.strip()}\n\n{part_c.strip()}"
        full_draft = self._ensure_complete_code_blocks(full_draft)
        full_draft = self._clean_hallucinated_links(full_draft)
        full_draft = self._ensure_cta_included(full_draft)

        word_count = len(full_draft.split())
        logger.info(f"Agent 5 generated multi-pass comprehensive draft ({word_count} words).")
        return {"draft_content": full_draft}
