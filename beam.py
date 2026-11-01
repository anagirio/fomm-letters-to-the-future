"""Talking to Beam (and a clearly-labelled demo mode when there is no token)."""

import os
import time
import threading
from collections import defaultdict

from huggingface_hub import InferenceClient

# Two ways to reach Beam: Reflection's own OpenAI-compatible API, or Hugging Face Inference Providers.
REFLECTION_KEY = os.getenv("REFLECTION_API_KEY")
TOKEN = os.getenv("HF_TOKEN")
if REFLECTION_KEY:
    MODEL = os.getenv("BEAM_MODEL", "Beam-1.0-501B-A23B")
    PROVIDER = "Reflection API"
else:
    MODEL = os.getenv("BEAM_MODEL", "reflection/Beam-1.0-501B-A23B")
    PROVIDER = os.getenv("BEAM_PROVIDER", "auto")

# Protect the credits of whoever hosts the Space.
PER_SESSION_LIMIT = int(os.getenv("BEAM_SESSION_LIMIT", "25"))
DAILY_LIMIT = int(os.getenv("BEAM_DAILY_LIMIT", "600"))

if REFLECTION_KEY:
    _client = InferenceClient(base_url="https://api.reflection.ai/openai/v1", api_key=REFLECTION_KEY)
elif TOKEN:
    _client = InferenceClient(provider=PROVIDER, api_key=TOKEN)
else:
    _client = None
_lock = threading.Lock()
_per_session = defaultdict(int)
_day = {"date": time.strftime("%Y-%m-%d"), "count": 0}


class LimitReached(Exception):
    pass


def demo_mode() -> bool:
    return _client is None


def _spend(session: str) -> None:
    with _lock:
        today = time.strftime("%Y-%m-%d")
        if _day["date"] != today:
            _day.update(date=today, count=0)
            _per_session.clear()
        if _per_session[session] >= PER_SESSION_LIMIT:
            raise LimitReached("You reached the limit of Beam calls for this session. Refresh to start over later.")
        if _day["count"] >= DAILY_LIMIT:
            raise LimitReached("The Space reached today's Beam budget. Please come back tomorrow.")
        _per_session[session] += 1
        _day["count"] += 1


THINKING = "_✨ Beam is thinking…_"
# Beam reasons before answering and the reasoning counts against max_tokens, so every call gets extra room.
REASONING_BUDGET = int(os.getenv("BEAM_REASONING_BUDGET", "16000"))


class EmptyAnswer(Exception):
    pass


def stream(messages, session: str, max_tokens: int = 1200, temperature: float = 0.7, demo_text: str = "",
           show_thinking: bool = True, effort: str = "medium", reasoning: int = REASONING_BUDGET):
    """Yield the growing answer. Raises LimitReached before calling Beam."""
    _spend(session)
    if demo_mode():
        text = "⚠️ Demo mode (no API key set), this is a canned answer, not Beam.\n\n" + demo_text
        out = ""
        for word in text.split(" "):
            out += word + " "
            time.sleep(0.01)
            yield out
        return
    if show_thinking:
        yield THINKING
    out = ""
    for chunk in _client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=max_tokens + reasoning,
        temperature=temperature,
        stream=True,
        # Without a cap Beam can spend the whole budget thinking about a long life and never answer.
        extra_body={"reasoning_effort": effort} if REFLECTION_KEY else None,
    ):
        if chunk.choices and chunk.choices[0].delta.content:
            out += chunk.choices[0].delta.content
            yield out
    if not out:
        raise EmptyAnswer()


def complete(messages, session: str, **kw) -> str:
    out = ""
    for out in stream(messages, session, show_thinking=False, **kw):
        pass
    return out
