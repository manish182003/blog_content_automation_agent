import re
from typing import List, Dict, Any,Optional

NOTION_SUPPORTED_LANGUAGES = {
    "abap", "arduino", "bash", "basic", "c", "clojure", "coffeescript", "cpp", "c#",
    "css", "dart", "diff", "docker", "elixir", "elm", "erlang", "flow", "fortran", "f#",
    "gherkin", "glsl", "go", "graphql", "groovy", "haskell", "html", "java", "javascript",
    "json", "julia", "kotlin", "latex", "less", "lisp", "livescript", "lua", "makefile",
    "markdown", "markup", "matlab", "mermaid", "nix", "objective-c", "ocaml", "pascal",
    "perl", "php", "plain text", "powershell", "prolog", "protobuf", "python", "r",
    "reason", "ruby", "rust", "sass", "scala", "scheme", "scss", "shell", "sql", "swift",
    "typescript", "vb.net", "verilog", "vhdl", "visual basic", "webassembly", "xml", "yaml"
}

def calculate_ngram_similarity(text1: str, text2: str, n: int = 4) -> float:
    """Calculate n-gram overlap similarity (Jaccard similarity) between two texts."""
    def extract_ngrams(text: str, n_size: int) -> set:
        words = re.findall(r'\b\w+\b', text.lower())
        if len(words) < n_size:
            return set()
        return set(tuple(words[i:i + n_size]) for i in range(len(words) - n_size + 1))

    ngrams1 = extract_ngrams(text1, n)
    ngrams2 = extract_ngrams(text2, n)

    if not ngrams1 or not ngrams2:
        return 0.0

    intersection = ngrams1.intersection(ngrams2)
    union = ngrams1.union(ngrams2)
    return len(intersection) / len(union) if union else 0.0

def create_text_block(text: str) -> List[Dict[str, Any]]:
    """Helper to wrap string in Notion rich_text format, respecting Notion's 2000 char block limit."""
    if not text:
        return []
    # Truncate or chunk if over Notion limit
    chunks = [text[i:i + 1900] for i in range(0, len(text), 1900)]
    return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]

def clean_markdown_content(md_content: str) -> str:
    """Strip HTML comments, metadata blocks, carriage returns, broken math brackets, and clean formatting for Notion."""
    # Normalize Windows CRLF line endings to LF
    cleaned = md_content.replace('\r\n', '\n').replace('\r', '\n')
    # Remove HTML comments like <!-- ... -->
    cleaned = re.sub(r'<!--.*?-->', '', cleaned, flags=re.DOTALL)
    # Remove frontmatter or Metadata blocks if present
    if cleaned.startswith("---"):
        parts = cleaned.split("---", 2)
        if len(parts) >= 3:
            cleaned = parts[2]
            
    # Strip 'Meta description:' block if it appears before main H1 title
    if re.search(r'(?i)^\s*meta\s*description\s*:', cleaned):
        cleaned = re.sub(r'(?is)^\s*meta\s*description\s*:.*?(?=\n#|\Z)', '', cleaned)

    # Strip standalone metadata lines or labels
    cleaned = re.sub(r'(?im)^\s*(meta\s*description|direct\s*answer|direct\s*answer\s*summary)\s*:.*$\n?', '', cleaned)
    cleaned = re.sub(r'(?im)^\s*(meta\s*description|direct\s*answer|direct\s*answer\s*summary)\s*:\s*$', '', cleaned)

    # Clean 'Question: ...' or 'Q1: ...' into clean markdown H3 headers
    cleaned = re.sub(r'(?im)^\s*(?:Question|Q\d*)\s*:\s*', '### ', cleaned)

    # Clean 'Answer: ...' or 'A: ...' or 'Ans: ...' label prefixes
    cleaned = re.sub(r'(?im)^\s*(?:Answer|Ans\d*|A)\s*:\s*', '', cleaned)

    # Clean broken isolated math brackets '[' and ']' on standalone lines
    cleaned = re.sub(r'(?m)^\s*\[\s*$\n?', '', cleaned)
    cleaned = re.sub(r'(?m)^\s*\]\s*$\n?', '', cleaned)
    # Clean raw LaTeX macros into clean text math symbols
    cleaned = re.sub(r'\\text\{([^}]+)\}!?', r'\1', cleaned)
    cleaned = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1 / \2)', cleaned)
    cleaned = re.sub(r'\\sqrt\{([^}]+)\}', r'√\1', cleaned)
    cleaned = re.sub(r'\\left\(', '(', cleaned)
    cleaned = re.sub(r'\\right\)', ')', cleaned)
    cleaned = re.sub(r'\^\\top', 'ᵀ', cleaned)
    return cleaned.strip()

def parse_markdown_table_to_notion(table_lines: List[str]) -> Optional[Dict[str, Any]]:
    """Parse a Markdown table block into Notion's native table block schema."""
    if not table_lines:
        return None

    # Filter out empty or whitespace lines
    lines = [l.strip() for l in table_lines if l.strip()]
    if len(lines) < 2:
        return None

    def split_row(row_str: str) -> List[str]:
        # Strip leading and trailing pipes
        s = row_str.strip()
        if s.startswith('|'):
            s = s[1:]
        if s.endswith('|'):
            s = s[:-1]
        return [cell.strip() for cell in s.split('|')]

    header_cells = split_row(lines[0])
    num_cols = len(header_cells)

    # Line 1 is header, line 2 is separator (e.g. |---|---|)
    start_idx = 1
    if len(lines) > 1 and re.match(r'^[|\s:-]+$', lines[1]):
        start_idx = 2

    table_rows = []
    # Add Header Row
    table_rows.append({
        "type": "table_row",
        "table_row": {
            "cells": [create_text_block(cell) for cell in header_cells]
        }
    })

    # Add Data Rows
    for row_str in lines[start_idx:]:
        cells = split_row(row_str)
        # Pad or truncate cells to match column count
        if len(cells) < num_cols:
            cells.extend([""] * (num_cols - len(cells)))
        elif len(cells) > num_cols:
            cells = cells[:num_cols]

        table_rows.append({
            "type": "table_row",
            "table_row": {
                "cells": [create_text_block(cell) for cell in cells]
            }
        })

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": num_cols,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows
        }
    }

def markdown_to_notion_blocks(md_content: str) -> List[Dict[str, Any]]:
    """
    Parse a Markdown document into structured Notion block objects.
    Supports H1, H2, H3, paragraphs, bullet points, callouts, code blocks, and native tables.
    """
    cleaned_md = clean_markdown_content(md_content)
    blocks = []
    lines = cleaned_md.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Code blocks
        if stripped.startswith("```"):
            raw_lang = stripped[3:].strip().lower()
            if raw_lang in ["py", "python3"]:
                lang = "python"
            elif raw_lang in ["js", "jsx"]:
                lang = "javascript"
            elif raw_lang in ["ts", "tsx"]:
                lang = "typescript"
            elif raw_lang in ["sh", "zsh"]:
                lang = "shell"
            elif raw_lang in NOTION_SUPPORTED_LANGUAGES:
                lang = raw_lang
            else:
                lang = "plain text"

            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1

            code_text = "\n".join(code_lines)
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "caption": [],
                    "rich_text": create_text_block(code_text),
                    "language": lang
                }
            })
            i += 1
            continue

        # Markdown Tables
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                table_lines.append(lines[i])
                i += 1
            table_block = parse_markdown_table_to_notion(table_lines)
            if table_block:
                blocks.append(table_block)
            continue

        # Headings
        if stripped.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": create_text_block(stripped[2:].strip())}
            })
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": create_text_block(stripped[3:].strip())}
            })
        elif stripped.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": create_text_block(stripped[4:].strip())}
            })
        # Bulleted lists
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": create_text_block(stripped[2:].strip())}
            })
        # Numbered lists
        elif re.match(r'^\d+\.\s', stripped):
            content = re.sub(r'^\d+\.\s', '', stripped)
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": create_text_block(content)}
            })
        # Callout block
        elif stripped.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": create_text_block(stripped[2:].strip()),
                    "icon": {"type": "emoji", "emoji": "💡"}
                }
            })
        # Regular paragraph
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": create_text_block(stripped)}
            })

        i += 1

    return blocks
