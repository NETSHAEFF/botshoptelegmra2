from __future__ import annotations

import html
import re


def format_text(value: str | None) -> str:
    """Convert simple markdown-like syntax to Telegram HTML-safe text."""

    if not value:
        return ""

    text = value.replace("\\n", "\n")
    placeholders: dict[str, str] = {}

    def _add_placeholder(prefix: str, html_value: str) -> str:
        key = f"ZZ{prefix}{len(placeholders)}ZZ"
        placeholders[key] = html_value
        return key

    def _replace_codeblock(match: re.Match[str]) -> str:
        content = match.group(1) or ""
        return _add_placeholder("CODEBLOCK", f"<pre>{html.escape(content)}</pre>")

    def _replace_inline_code(match: re.Match[str]) -> str:
        content = match.group(1) or ""
        return _add_placeholder("INLINE", f"<code>{html.escape(content)}</code>")

    text = re.sub(r"```(.*?)```", _replace_codeblock, text, flags=re.S)
    text = re.sub(r"`([^`]+)`", _replace_inline_code, text)

    text = html.escape(text)

    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<u>\1</u>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", text)

    for key, html_value in placeholders.items():
        text = text.replace(key, html_value)

    return text
