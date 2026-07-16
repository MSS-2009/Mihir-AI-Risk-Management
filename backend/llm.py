"""Anthropic client, shared by every agent that interprets (never computes).

Centralised so the whole graph degrades gracefully to a deterministic
fallback when no API key is present, the no-key path must work end to end.
"""
import os

from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

try:
    from anthropic import Anthropic

    _key = os.environ.get("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=_key) if _key else None
except Exception as e:  # pragma: no cover - defensive init
    print(f"Anthropic client init failed: {e}")
    client = None


def ai_enabled() -> bool:
    return client is not None


def extract_text(msg) -> str:
    """Pull only the text blocks. Modern Claude models can return thinking
    blocks first, so `msg.content[0]` is not reliably the answer."""
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip()
