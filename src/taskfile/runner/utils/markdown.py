"""Markdown rendering utilities for task runner."""

from __future__ import annotations

try:
    from clickmd import MarkdownRenderer
    _HAS_CLICKMD = True
except ImportError:
    _HAS_CLICKMD = False


def render_md(text: str) -> None:
    """Render markdown text via clickmd (falls back to plain print)."""
    if _HAS_CLICKMD:
        MarkdownRenderer(use_colors=True).render_markdown_with_fences(text)
    else:
        print(text)


def render_codeblock(lang: str, code: str) -> None:
    """Render a code block via clickmd (falls back to plain print)."""
    if _HAS_CLICKMD:
        MarkdownRenderer(use_colors=True).codeblock(lang, code)
    else:
        print(code)


# Backward-compatible alias
_md = render_md
