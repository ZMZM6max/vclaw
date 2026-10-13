#!/usr/bin/env python3
"""
Telegram Bot Message Receiver — Polling Mode

Connects to Telegram Bot API via long-polling, receives real updates,
and prints the full raw JSON for inspection.

Usage:
    python scripts/telegram_receiver.py

Requirements:
    pip install requests python-dotenv

Network note:
    If you are in mainland China, Telegram API is blocked.
    Set a proxy in .env (HTTPS_PROXY=http://127.0.0.1:7890) or use a VPN.
"""

import os
import sys
import time
import json
import signal
from pathlib import Path

import requests
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
#  Load environment
# --------------------------------------------------------------------------- #
ENV_PATH = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip().strip('"').strip("'")
PROXY_URL = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("https_proxy") or os.getenv("http_proxy")

if not TOKEN:
    print("[ERROR] TELEGRAM_BOT_TOKEN not found in .env")
    sys.exit(1)

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# --------------------------------------------------------------------------- #
#  HTTP session with optional proxy
# --------------------------------------------------------------------------- #
session = requests.Session()
if PROXY_URL:
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}
    print(f"[INFO] Using proxy: {PROXY_URL}")

# --------------------------------------------------------------------------- #
#  Graceful shutdown
# --------------------------------------------------------------------------- #
_running = True

def _on_sigint(signum, frame):
    global _running
    print("\n[INFO] Received interrupt, stopping...")
    _running = False

signal.signal(signal.SIGINT, _on_sigint)

# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _banner():
    print("=" * 70)
    print("  Telegram Bot Receiver — Polling Mode")
    print("=" * 70)
    print(f"  Bot token : {TOKEN[:10]}...{TOKEN[-6:]}")
    print(f"  Proxy     : {PROXY_URL or '(none)'}")
    print(f"  API URL   : {BASE_URL}/getUpdates")
    print("=" * 70)
    print("  Send a message to your bot in Telegram to see the raw payload.")
    print("  Press Ctrl+C to stop.\n")


def _print_update(update: dict):
    """Pretty-print one Update object with field statistics."""
    update_id = update.get("update_id", "?")

    # Determine which sub-event is present
    event_key = None
    for key in ("message", "edited_message", "channel_post", "edited_channel_post",
                "callback_query", "inline_query", "chosen_inline_result",
                "shipping_query", "pre_checkout_query", "poll", "poll_answer",
                "my_chat_member", "chat_member", "chat_join_request"):
        if key in update:
            event_key = key
            break

    print(f"\n{'─' * 70}")
    print(f"  UPDATE ID: {update_id}  |  EVENT TYPE: {event_key or 'unknown'}")
    print(f"{'─' * 70}")

    # Full JSON
    print("[RAW JSON]")
    print(json.dumps(update, indent=2, ensure_ascii=False))

    # Quick field stats if it's a message
    msg = update.get("message") or update.get("edited_message")
    if isinstance(msg, dict):
        print(f"\n[FIELD STATS]")
        print(f"  Top-level update keys : {list(update.keys())}")
        print(f"  Message keys          : {list(msg.keys())}")
        if "from" in msg:
            print(f"  From user             : id={msg['from'].get('id')}, "
                  f"name={msg['from'].get('first_name')}, "
                  f"username={msg['from'].get('username')}")
        if "chat" in msg:
            print(f"  Chat                  : id={msg['chat'].get('id')}, type={msg['chat'].get('type')}")
        if "text" in msg:
            print(f"  Text content          : {msg['text']!r}")
        if "date" in msg:
            print(f"  Date (unix)           : {msg['date']}")
        if "entities" in msg:
            print(f"  Entities              : {msg['entities']}")
        if "photo" in msg:
            print(f"  Photo count           : {len(msg['photo'])}")
        if "document" in msg:
            print(f"  Document              : {msg['document']}")
        if "voice" in msg:
            print(f"  Voice                 : {msg['voice']}")
        if "caption" in msg:
            print(f"  Caption               : {msg['caption']!r}")

    print(f"{'─' * 70}\n")


# --------------------------------------------------------------------------- #
#  Main loop
# --------------------------------------------------------------------------- #

def main():
    _banner()

    offset = 0
    empty_count = 0

    while _running:
        try:
            resp = session.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "limit": 100, "timeout": 30},
                timeout=40,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok"):
                print(f"[ERROR] Telegram API returned error: {data}")
                time.sleep(5)
                continue

            updates = data.get("result", [])

            if not updates:
                empty_count += 1
                # Print a heartbeat every 10 empty polls so the user knows we're alive
                if empty_count % 10 == 0:
                    print(f"[...] No new messages yet ({empty_count} empty polls). "
                          f"Send something to your bot!")
                time.sleep(2)
                continue

            # Reset heartbeat counter when we get messages
            empty_count = 0

            for update in updates:
                _print_update(update)
                # advance offset so Telegram marks this update as delivered
                offset = update["update_id"] + 1

        except requests.exceptions.ProxyError as e:
            print(f"[ERROR] Proxy connection failed: {e}")
            print("        Check your proxy settings in .env (HTTPS_PROXY=...)")
            time.sleep(5)

        except requests.exceptions.ConnectionError as e:
            print(f"[ERROR] Cannot connect to Telegram API: {e}")
            print("        If you are in mainland China, Telegram is blocked.")
            print("        Set a proxy in .env or enable your VPN.")
            time.sleep(5)

        except requests.exceptions.Timeout:
            print("[WARN] Long-polling timeout, retrying...")
            continue

        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            time.sleep(5)

    print("[INFO] Receiver stopped.")


if __name__ == "__main__":
    main()
