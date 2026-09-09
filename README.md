# Autonomous Tech Blog Generator System

An autonomous, multi-agent Python system that runs once a day to research, write, SEO-audit, quality-check, and publish exactly one technical blog post (strictly **AI** or **Mobile App Development**) to a Notion database (which auto-syncs to your personal site [manishjoshi.online](https://www.manishjoshi.online/)).

Uses **Groq's free-tier LLM API** (`openai/gpt-oss-120b` with fallback to `qwen/qwen3.8-27b`) for every agent, backed by automatic retries, fallback datasets, and reliability logging.

---

## 🌟 System Architecture & DAG Agents

The system uses a state machine DAG orchestrator (`orchestrator.py`) passing shared context through 9 specialized agents in sequence:

1. **Keyword Research Agent** (`agents/keyword_agent.py`): Finds 3–5 low-competition tech keywords via Google Autocomplete & Trends. Fallback: `data/seed_keywords.json`.
2. **Tech News Agent** (`agents/news_agent.py`): Fetches 24–48h news via RSS feeds (TechCrunch AI, The Verge, Ars Technica, Android Authority, Hacker News). Fallback: `data/cached_news.json`.
3. **Past-Blog Summarizer Agent** (`agents/past_blog_agent.py`): Queries Notion via `notion-client` to retrieve published topics and prevent duplicate posts. Fallback: proceed with cached summary.
4. **Topic Selection Agent** (`agents/topic_agent.py`): Synthesizes keywords, news, and past blogs to pick **exactly ONE topic** (strictly AI or Mobile App Dev) with 3–5 supporting news facts.
5. **Content Generation Agent** (`agents/content_agent.py`): Writes the full article in Markdown format enforcing the coffee-chat style prompt (short sentences, zero AI clichés, concrete code examples, natural CTA).
6. **SEO Validator Agent** (`agents/seo_agent.py`): Evaluates Classic Google SEO (keyword placement, H1/H2 hierarchy) and GEO/AI-Search readiness (direct answers, scannable tables/lists). Pass threshold: ≥75/100.
7. **Quality / Groundedness Auditor Agent** (`agents/groundedness_agent.py`): LLM-as-Judge for relevance, faithfulness, and factual groundedness, plus a 4-gram plagiarism checker (<35% overlap threshold). Loops back to Agent 5 for targeted rewrites on audit failure (max 3 attempts).
8. **Metadata Agent** (`agents/metadata_agent.py`): Generates `SEO Title`, `Meta Description`, `URL Slug`, `Excerpt`, and `Category`.
9. **Publisher Agent** (`agents/publisher_agent.py`): Converts Markdown to Notion blocks, handles staging (`Published: False` -> `True`), or writes output locally in dry-run mode.

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Groq API Key
- Notion Integration Token & Database ID

### 2. Environment Configuration
Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

Your `.env` file should contain:
```ini
GROQ_API_KEY=gsk_your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=qwen/qwen3.8-27b

NOTION_API_KEY=ntn_your_notion_api_key
NOTION_DATABASE_ID=3d2fa265263d80568695c58f40631822

# Daily execution schedule (24-hour format local time)
RUN_HOUR=8
RUN_MINUTE=0

# Notifications (optional)
NOTIFICATION_WEBHOOK_URL=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

DRY_RUN=true
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🛠️ Usage Commands

### 1. Run in Dry-Run Mode (Default)
Generates a full blog post and audits locally without writing to Notion:
```bash
python main.py --run-now --dry-run
```
Output files are saved to `output/draft_<timestamp>.md`.

### 2. Run in Live Mode
Executes the full pipeline and publishes directly to Notion:
```bash
python main.py --run-now --live
```

### 3. Start Daily Background Scheduler
Runs the job automatically every day at 08:00 (configurable via `RUN_HOUR`):
```bash
python main.py --schedule
```

### 4. View Reliability Metrics
Inspects historical run stats recorded in `run_logs.db`:
```bash
python main.py --metrics
```

### 5. Run Automated Test Suite
Executes the unit tests for all 9 agents and text utilities:
```bash
python -m pytest tests/test_agents.py
```

---

## 📊 Notion Property Schema Alignment

The system maps Notion page properties directly to your Notion database (`3d2fa265263d80568695c58f40631822`):

| Notion Property Name | Notion Property Type | Example Content |
| :--- | :--- | :--- |
| `Title` | `title` | How to Build a Flutter App with Integrated AI |
| `SEO Title` | `rich_text` | Build a Flutter App with AI Integration: Cloud vs On-Device |
| `Meta Description` | `rich_text` | Learn how to build a Flutter app with AI integration... |
| `Category` | `rich_text` | `Mobile App Development` or `AI` |
| `Slug` | `rich_text` | `build-flutter-app-with-ai-integration` |
| `Excerpt` | `rich_text` | Discover how to create a Flutter app with AI... |
| `Published` | `checkbox` | `True` (live) or `False` (draft/needs-review) |

---

## 🛡️ Reliability & Edge Case Protections

- **Groq API Pacing & Retries**: Uses `tenacity` exponential backoff with multi-tier model fallbacks (`openai/gpt-oss-120b` -> `qwen/qwen3.8-27b`). Handles HTTP 429 rate limit delays cleanly.
- **Idempotency Check**: Checks `run_logs.db` before executing live runs; prevents publishing more than one post per calendar day.
- **Graceful Degradation**: Skips dead RSS feeds, falls back to `data/cached_news.json`, and uses `data/seed_keywords.json` if Google Trends is blocked.
- **Staging Notion Writes**: Writes Notion page blocks in draft state (`Published: False`) first, verifies block creation, and only flips to `Published: True` upon full verification.
