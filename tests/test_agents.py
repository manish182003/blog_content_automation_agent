import pytest
from unittest.mock import MagicMock, patch

from agents.keyword_agent import KeywordResearchAgent
from agents.news_agent import TechNewsAgent
from agents.past_blog_agent import PastBlogSummarizerAgent
from agents.topic_agent import TopicSelectionAgent
from agents.content_agent import ContentGenerationAgent
from agents.seo_agent import SEOValidatorAgent
from agents.groundedness_agent import GroundednessAuditorAgent
from agents.metadata_agent import MetadataAgent
from agents.publisher_agent import PublisherAgent

from utils_text import calculate_ngram_similarity, markdown_to_notion_blocks

@pytest.fixture
def mock_llm():
    mock = MagicMock()
    mock.generate.return_value = "This is a test blog post draft. We are building AI Flutter apps over coffee."
    mock.generate_json.return_value = {
        "candidates": [{"keyword": "Flutter AI", "category": "AI", "difficulty": "low", "interest_score": 80, "rationale": "High volume"}],
        "chosen_topic": "Building Flutter AI Apps",
        "target_keyword": "Flutter AI",
        "category": "AI",
        "angle": "Hands-on guide",
        "supporting_facts": ["Fact 1", "Fact 2"],
        "google_seo_score": 85,
        "geo_ai_search_score": 88,
        "seo_passed": True,
        "relevance_score": 90,
        "faithfulness_score": 95,
        "groundedness_score": 92,
        "passed": True,
        "seo_title": "Flutter AI Guide",
        "meta_description": "Learn Flutter AI",
        "slug": "flutter-ai-guide",
        "excerpt": "Excerpt text"
    }
    return mock

def test_ngram_similarity():
    t1 = "Flutter apps use local small language models for low latency."
    t2 = "Flutter apps use local small language models for low latency."
    t3 = "Completely unrelated content about cooking recipes."
    
    assert calculate_ngram_similarity(t1, t2) == 1.0
    assert calculate_ngram_similarity(t1, t3) == 0.0

def test_markdown_to_notion_blocks():
    md = "# Heading 1\n\nParagraph text\n\n## Heading 2\n\n- Item 1\n- Item 2"
    blocks = markdown_to_notion_blocks(md)
    assert len(blocks) == 5
    assert blocks[0]["type"] == "heading_1"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[2]["type"] == "heading_2"
    assert blocks[3]["type"] == "bulleted_list_item"

def test_keyword_agent_fallback(mock_llm):
    agent = KeywordResearchAgent(llm_client=mock_llm)
    with patch.object(agent, '_fetch_autocomplete_suggestions', side_effect=Exception("Network error")):
        res = agent.run({})
        assert "keyword_candidates" in res
        assert len(res["keyword_candidates"]) > 0

def test_news_agent_fallback(mock_llm):
    agent = TechNewsAgent(llm_client=mock_llm)
    with patch.object(agent, '_fetch_feed', return_value=[]):
        res = agent.run({})
        assert "news_items" in res
        assert len(res["news_items"]) > 0

def test_past_blog_agent_fallback(mock_llm):
    agent = PastBlogSummarizerAgent(llm_client=mock_llm)
    with patch.object(agent, '_query_notion_posts', return_value=[]):
        res = agent.run({})
        assert "past_blog_summary" in res
        assert res["past_blog_summary"]["post_count"] == 0

def test_topic_selection_agent(mock_llm):
    agent = TopicSelectionAgent(llm_client=mock_llm)
    res = agent.run({
        "keyword_candidates": [{"keyword": "Test"}],
        "news_items": [],
        "past_blog_summary": {},
        "covered_topics": []
    })
    assert res["chosen_topic"] == "Building Flutter AI Apps"
    assert res["category"] in ["AI", "Mobile App Development", "Backend Systems", "AI Mathematics & CS Foundations", "AI & Agentic Systems"]

def test_content_generation_agent(mock_llm):
    agent = ContentGenerationAgent(llm_client=mock_llm)
    res = agent.run({"chosen_topic": "Test Topic", "target_keyword": "Test"})
    assert "draft_content" in res
    assert len(res["draft_content"]) > 0

def test_seo_validator_agent(mock_llm):
    agent = SEOValidatorAgent(llm_client=mock_llm)
    res = agent.run({"draft_content": "Draft", "target_keyword": "Test"})
    assert res["seo_passed"] is True
    assert res["google_seo_score"] == 85

def test_groundedness_auditor_agent(mock_llm):
    agent = GroundednessAuditorAgent(llm_client=mock_llm)
    res = agent.run({
        "draft_content": "Draft",
        "chosen_topic": "Test",
        "supporting_facts": [],
        "news_items": []
    })
    assert res["groundedness_passed"] is True
    assert res["groundedness_overall_score"] >= 75.0

def test_metadata_agent(mock_llm):
    agent = MetadataAgent(llm_client=mock_llm)
    res = agent.run({"chosen_topic": "Test", "target_keyword": "Test", "category": "AI", "draft_content": "Draft"})
    assert "metadata" in res
    assert res["metadata"]["category"] in ["AI", "Mobile App Development"]

def test_publisher_agent_dry_run(mock_llm, tmp_path):
    agent = PublisherAgent(llm_client=mock_llm)
    with patch("config.OUTPUT_DIR", tmp_path):
        res = agent.run({
            "chosen_topic": "Test Topic",
            "metadata": {"slug": "test-slug"},
            "draft_content": "Draft content",
            "dry_run": True,
            "seo_passed": True,
            "groundedness_passed": True
        })
        assert res["published_live"] is False
        assert "output_path" in res
