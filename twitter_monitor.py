#!/usr/bin/env python3
"""
monitor.py - Track AI researchers who've left frontier labs and may be starting something new.
"""

import os
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "results.jsonl")
SEEN_FILE   = os.path.join(os.path.dirname(__file__), "seen_ids.json")

LABS = [
    "OpenAI", "Anthropic", "xAI", "DeepMind", "Google DeepMind",
    "Meta AI", "FAIR", "Mistral", "Cohere", "Inflection", "Adept",
    "Character.AI", "Stability AI", "Runway", "Scale AI", "AI2",
    "Allen Institute", "Cerebras", "Groq", "Together AI"
]

DEPARTURE_SIGNALS = [
    "left OpenAI", "leaving OpenAI", "my last day at OpenAI",
    "left Anthropic", "leaving Anthropic", "my last day at Anthropic",
    "left DeepMind", "leaving DeepMind", "my last day at DeepMind",
    "left xAI", "leaving xAI",
    "left Meta AI", "leaving Meta AI", "left FAIR", "leaving FAIR",
    "left Mistral", "leaving Mistral",
    "left Cohere", "leaving Cohere",
    "moving on from", "next chapter", "my last day",
]

STARTUP_SIGNALS = [
    "working on something new", "building something", "stealth",
    "can't say yet", "tbd", "to be announced", "stay tuned",
    "founding", "co-founder", "new venture", "new company",
    "starting something", "exciting news soon", "more soon",
]

# Build search queries (Twitter limits query length, so we chunk)
def build_queries():
    queries = []
    # First-person departures from each lab (no startup signal required — we score that separately)
    for lab in ["OpenAI", "Anthropic", "DeepMind", "xAI", "Meta AI", "Mistral", "Cohere"]:
        q = f'("left {lab}" OR "leaving {lab}" OR "last day at {lab}" OR "years at {lab}") lang:en -is:retweet'
        queries.append(q)
    # Catch "today was my last day" + lab combos
    q2 = '("my last day" OR "left Google DeepMind" OR "left Google" OR "left OpenAI" OR "left Anthropic" OR "left xAI" OR "left Meta AI") (AI OR research OR ML OR LLM OR researcher OR engineer) lang:en -is:retweet'
    queries.append(q2)
    return queries

# ── Twitter API ───────────────────────────────────────────────────────────────

def search_recent(query, max_results=100):
    params = urllib.parse.urlencode({
        "query": query,
        "max_results": max_results,
        "tweet.fields": "created_at,author_id,text,entities",
        "expansions": "author_id",
        "user.fields": "name,username,description,public_metrics",
    })
    url = f"https://api.twitter.com/2/tweets/search/recent?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {BEARER_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

# ── Filtering ─────────────────────────────────────────────────────────────────

# News/media/influencer account keywords to reject
MEDIA_BIO_SIGNALS = [
    "journalist", "reporter", "editor", "news", "newsletter", "media",
    "columnist", "correspondent", "breaking", "bloomberg", "techcrunch",
    "wired", "forbes", "wsj", "nyt", "the verge", "podcaster",
]

FIRST_PERSON_SIGNALS = [
    "i left", "i'm leaving", "i am leaving", "my last day", "i've decided",
    "i have decided", "moving on from", "i resigned", "stepping down",
    "my time at", "after x years at", "after n years at", "years at",
    "i spent", "i'm done at", "i am done at", "today was my last",
    "was my last day", "left google", "left openai", "left anthropic",
    "left deepmind", "left xai", "left meta", "left mistral", "left cohere",
    "left inflection", "left adept",
]

def is_first_person_departure(text):
    t = text.lower()
    return any(sig in t for sig in FIRST_PERSON_SIGNALS)

def is_media_account(user_desc, username):
    desc = (user_desc or "").lower()
    return any(sig in desc for sig in MEDIA_BIO_SIGNALS)

def is_retweet_or_quote_news(text):
    """Reject tweets that are purely reporting on someone else's departure."""
    t = text.lower()
    third_person = ["he is leaving", "she is leaving", "they are leaving",
                    "has left", "have left", "co-founder leaving", "co-founder left",
                    "said he is", "said she is", "announced he", "announced she"]
    return any(sig in t for sig in third_person)

# ── Scoring ───────────────────────────────────────────────────────────────────

def score_tweet(text, user_desc="", followers=0, username=""):
    text_lower = text.lower()
    desc_lower = (user_desc or "").lower()

    # Hard filters
    if followers < 500:
        return 0
    if is_media_account(user_desc, username):
        return 0
    if not is_first_person_departure(text_lower):
        return 0
    if is_retweet_or_quote_news(text_lower):
        return 0

    score = 0

    # Lab mentioned
    for lab in LABS:
        if lab.lower() in text_lower:
            score += 3

    # Startup / ambiguity signals
    for sig in STARTUP_SIGNALS:
        if sig.lower() in text_lower:
            score += 3

    # Researcher/engineer in bio
    researcher_bio = ["researcher", "engineer", "scientist", "phd", "ml", "ai", "llm", "research", "rl ", "nlp"]
    for kw in researcher_bio:
        if kw in desc_lower:
            score += 1

    # Bonus for ambiguity (stealth/tbd = high signal)
    high_signal = ["stealth", "tbd", "can't say", "cannot say", "more soon", "stay tuned", "working on something"]
    for sig in high_signal:
        if sig in text_lower:
            score += 4

    return score

# ── Main ──────────────────────────────────────────────────────────────────────

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def run():
    if not BEARER_TOKEN:
        print("ERROR: TWITTER_BEARER_TOKEN not set")
        return

    seen = load_seen()
    queries = build_queries()
    new_results = []

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Running {len(queries)} queries...")

    for i, query in enumerate(queries):
        print(f"  Query {i+1}/{len(queries)}: {query[:80]}...")
        data = search_recent(query, max_results=100)
        if not data or "data" not in data:
            time.sleep(2)
            continue

        # Build user lookup
        users = {}
        for u in data.get("includes", {}).get("users", []):
            users[u["id"]] = u

        for tweet in data["data"]:
            tid = tweet["id"]
            if tid in seen:
                continue
            seen.add(tid)

            author = users.get(tweet.get("author_id"), {})
            followers = author.get("public_metrics", {}).get("followers_count", 0)
            score = score_tweet(tweet["text"], author.get("description", ""), followers, author.get("username", ""))

            if score >= 5:  # threshold
                result = {
                    "id": tid,
                    "score": score,
                    "text": tweet["text"],
                    "created_at": tweet.get("created_at"),
                    "author": {
                        "id": author.get("id"),
                        "name": author.get("name"),
                        "username": author.get("username"),
                        "bio": author.get("description"),
                        "followers": author.get("public_metrics", {}).get("followers_count"),
                    },
                    "url": f"https://twitter.com/i/web/status/{tid}",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                new_results.append(result)

        time.sleep(1.5)  # rate limit buffer

    # Save results
    if new_results:
        with open(OUTPUT_FILE, "a") as f:
            for r in new_results:
                f.write(json.dumps(r) + "\n")
        print(f"\n✅ {len(new_results)} new matches saved to results.jsonl")
        for r in sorted(new_results, key=lambda x: x["score"], reverse=True)[:10]:
            print(f"\n  [{r['score']}] @{r['author'].get('username')} ({r['author'].get('followers', '?')} followers)")
            print(f"  {r['text'][:200]}")
            print(f"  {r['url']}")
    else:
        print("No new matches this run.")

    save_seen(seen)

if __name__ == "__main__":
    run()
