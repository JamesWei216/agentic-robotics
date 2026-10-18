#!/usr/bin/env python3
"""Thin DeepSeek (OpenAI-compatible) client.

The API key is resolved in this order:
  1. $DEEPSEEK_API_KEY
  2. OpenClaw auth store (~/.openclaw/agents/main/agent/openclaw-agent.sqlite)

Nothing here ever prints the key.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "agent.json").read_text())
_LLM = CFG["llm"]

AUTH_DB = Path(os.path.expanduser("~/.openclaw/agents/main/agent/openclaw-agent.sqlite"))


def api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    con = sqlite3.connect(f"file:{AUTH_DB}?mode=ro", uri=True)
    try:
        row = con.execute("select store_json from auth_profile_store limit 1").fetchone()
    finally:
        con.close()
    if not row:
        raise RuntimeError("no API key: set DEEPSEEK_API_KEY")
    profiles = json.loads(row[0])["profiles"]
    for name, prof in profiles.items():
        if name.startswith("deepseek:") and prof.get("key"):
            return prof["key"]
    raise RuntimeError("no deepseek profile in auth store")


class LLMError(RuntimeError):
    pass


def chat(messages, *, model: str | None = None, json_mode: bool = False,
         temperature: float | None = None, max_tokens: int = 8000,
         think: bool | None = None, retries: int | None = None) -> str:
    """Return the assistant message content as text.

    `think=False` disables the model's reasoning trace. Use it for schema-bound
    JSON stages (planner / codegen): there the reasoning budget can swallow the
    whole max_tokens and leave `content` empty.
    """
    model = model or _LLM["model"]
    temperature = _LLM["temperature"] if temperature is None else temperature
    retries = _LLM["max_retries"] if retries is None else retries

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if think is False:
        payload["thinking"] = {"type": "disabled"}
    elif think is True:
        payload["thinking"] = {"type": "enabled"}

    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            _LLM["base_url"].rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key()}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=_LLM["timeout_s"]) as resp:
                body = json.loads(resp.read())
            choice = body["choices"][0]
            content = choice["message"].get("content") or ""
            if not content.strip():
                raise LLMError(
                    f"empty content (finish_reason={choice.get('finish_reason')}, "
                    f"usage={body.get('usage')})")
            return content
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            last_err = f"HTTP {e.code}: {detail}"
            # 4xx other than 429 is not worth retrying
            if 400 <= e.code < 500 and e.code != 429:
                break
        except Exception as e:  # noqa: BLE001 - network/timeout/json
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (attempt + 1))
    raise LLMError(f"LLM call failed after {retries + 1} attempts: {last_err}")


def chat_json(messages, **kw) -> dict:
    """Chat with JSON output; tolerant of fenced code blocks."""
    kw.setdefault("json_mode", True)
    kw.setdefault("think", False)
    text = chat(messages, **kw)
    return parse_json(text)


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


if __name__ == "__main__":
    print(chat([{"role": "user", "content": "reply with the single word: ok"}],
               max_tokens=16))
