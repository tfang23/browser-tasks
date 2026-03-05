#!/usr/bin/env python3
"""
digest.py - Generate and send a daily digest of researcher departure signals.
"""

import json
import os
from datetime import datetime, timezone, timedelta

RESULTS_FILE       = os.path.join(os.path.dirname(__file__), "results.jsonl")
APOLLO_RESULTS_FILE= os.path.join(os.path.dirname(__file__), "apollo_results.jsonl")
SENT_FILE          = os.path.join(os.path.dirname(__file__), "digest_sent.json")

def load_sent():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE) as f:
            return set(json.load(f))
    return set()

def save_sent(sent):
    with open(SENT_FILE, "w") as f:
        json.dump(list(sent), f)

def load_results_since(hours=168):  # 7 days
    if not os.path.exists(RESULTS_FILE):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    with open(RESULTS_FILE) as f:
        for line in f:
            try:
                r = json.loads(line)
                fetched = datetime.fromisoformat(r["fetched_at"])
                if fetched >= cutoff:
                    results.append(r)
            except:
                pass
    return results

def format_digest(results, sent):
    new = [r for r in results if r["id"] not in sent]
    if not new:
        return None, []

    # Sort by score desc, dedupe by author
    seen_authors = set()
    deduped = []
    for r in sorted(new, key=lambda x: x["score"], reverse=True):
        username = r["author"].get("username", "")
        if username not in seen_authors:
            seen_authors.add(username)
            deduped.append(r)

    lines = [f"🔬 **AI Lab Departure Radar** — {datetime.now().strftime('%b %d, %Y')}\n"]
    lines.append(f"Found **{len(deduped)}** new signal(s) in the last 24h:\n")

    for i, r in enumerate(deduped[:15], 1):
        author = r["author"]
        name = author.get("name", "Unknown")
        username = author.get("username", "?")
        followers = author.get("followers")
        bio = author.get("bio", "")
        text = r["text"]
        url = r["url"]
        score = r["score"]

        followers_str = f"{followers:,}" if followers else "?"
        bio_str = f"\n   📋 _{bio[:100]}_" if bio else ""

        lines.append(
            f"**{i}. @{username}** ({followers_str} followers) [score: {score}]{bio_str}\n"
            f"   {text[:280]}\n"
            f"   🔗 {url}\n"
        )

    return "\n".join(lines), [r["id"] for r in deduped[:15]]

def load_apollo_results(hours=168):
    if not os.path.exists(APOLLO_RESULTS_FILE):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results, seen_ids = [], set()
    with open(APOLLO_RESULTS_FILE) as f:
        for line in f:
            try:
                r = json.loads(line)
                fetched = datetime.fromisoformat(r["fetched_at"])
                if fetched >= cutoff and r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    results.append(r)
            except:
                pass
    return results

def format_apollo_section(results, sent):
    new = [r for r in results if r["id"] not in sent]
    if not new:
        return "", []
    lines = ["\n📊 *Apollo — Stealth Founders w/ Lab Background:*\n"]
    for r in new[:10]:
        name = r.get("name", "?")
        title = (r.get("title") or "")[:45]
        company = r.get("company", "?")
        linkedin = r.get("linkedin_url", "")
        link = f"\n   🔗 {linkedin}" if linkedin else ""
        lines.append(f"• *{name}* — {title} @ _{company}_{link}")
    return "\n".join(lines), [r["id"] for r in new[:10]]

def run():
    results = load_results_since(hours=168)
    sent = load_sent()
    digest, new_ids = format_digest(results, sent)

    apollo_results = load_apollo_results(hours=168)
    apollo_section, apollo_ids = format_apollo_section(apollo_results, sent)

    if not digest and not apollo_section:
        print("Nothing new to digest.")
        return

    print(digest or "")
    print(apollo_section or "")

    sent.update(new_ids)
    sent.update(apollo_ids)
    save_sent(sent)

if __name__ == "__main__":
    run()
