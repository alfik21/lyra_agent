#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CFG_PATH = BASE_DIR / "config.json"
HISTORY_PATH = BASE_DIR / "lyra_project" / "jądro" / "HistoriaChatGPT.json"


def load_cfg():
    if not CFG_PATH.exists():
        return {}
    try:
        return json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_history():
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def append_history(role, content):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = load_history()
    data.append({
        "time": datetime.now().isoformat(),
        "role": role,
        "content": content
    })
    HISTORY_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def main():
    try:
        import openai
    except ImportError:
        print("Brak biblioteki openai. Zainstaluj: pip install openai")
        sys.exit(1)

    cfg = load_cfg()
    api_key = cfg.get("openai_api_key") or cfg.get("api_key")
    if not api_key:
        print("Brak klucza API w config.json (openai_api_key).")
        sys.exit(1)

    model = cfg.get("default_cloud_model") or cfg.get("openai_model") or "gpt-4o"
    client = openai.OpenAI(api_key=api_key)

    messages = []
    print("ChatGPT logger online. 'exit' aby wyjść.")

    while True:
        try:
            user_text = input("Ty > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit", ":q"):
            break

        append_history("user", user_text)
        messages.append({"role": "user", "content": user_text})

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=30
            )
            reply = response.choices[0].message.content
        except Exception as e:
            reply = f"[ERROR] {e}"

        print(reply)
        append_history("assistant", reply)
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
