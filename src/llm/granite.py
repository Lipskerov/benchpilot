#!/usr/bin/env python3
"""
IBM Granite on watsonx.ai — thin REST client.

Reads credentials from environment / .env:
  WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL, GRANITE_MODEL_ID
Provides text and JSON generation. If credentials are absent, is_configured()
returns False and callers use their grounded offline path.
"""

import json
import os
import re
import time
from typing import Dict, Optional

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

API_KEY = os.getenv("WATSONX_API_KEY", "")
PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "")
URL = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").rstrip("/")
MODEL_ID = os.getenv("GRANITE_MODEL_ID", "ibm/granite-3-8b-instruct")
_IAM = "https://iam.cloud.ibm.com/identity/token"

_token_cache: Dict[str, float] = {"token": "", "exp": 0.0}


def is_configured() -> bool:
    return bool(API_KEY and PROJECT_ID)


def _iam_token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["exp"] - 60 > now:
        return _token_cache["token"]
    resp = requests.post(
        _IAM,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["exp"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


def generate(prompt: str, max_new_tokens: int = 700, temperature: float = 0.2) -> str:
    """Call Granite text generation. Raises on any failure (caller falls back)."""
    if not is_configured():
        raise RuntimeError("watsonx not configured")
    body = {
        "model_id": MODEL_ID,
        "project_id": PROJECT_ID,
        "input": prompt,
        "parameters": {
            "decoding_method": "greedy" if temperature <= 0 else "sample",
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "repetition_penalty": 1.05,
        },
    }
    resp = requests.post(
        f"{URL}/ml/v1/text/generation?version=2024-05-31",
        headers={"Authorization": f"Bearer {_iam_token()}", "Content-Type": "application/json"},
        json=body,
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["results"][0]["generated_text"].strip()


def generate_json(prompt: str, max_new_tokens: int = 900) -> Optional[Dict]:
    """Ask Granite for JSON and parse the first JSON object/array in the reply."""
    raw = generate(prompt + "\n\nReturn ONLY valid JSON, no prose.", max_new_tokens, 0.1)
    return _extract_json(raw)


def _extract_json(raw: str) -> Optional[Dict]:
    m = re.search(r"\{.*\}|\[.*\]", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


if __name__ == "__main__":
    print("configured:", is_configured(), "| model:", MODEL_ID)
    if is_configured():
        print(generate("In one sentence, what is triple-negative breast cancer?", 80))
