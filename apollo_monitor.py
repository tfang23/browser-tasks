#!/usr/bin/env python3
"""
apollo_monitor.py - Find founders/CEOs at stealth/new companies who previously worked at frontier AI labs.
Uses Apollo.io People API Search.
"""

import os, json, time, urllib.request, urllib.parse
from datetime import datetime, timezone

APOLLO_KEY   = os.environ.get("APOLLO_API_KEY", "")
OUTPUT_FILE  = os.path.join(os.path.dirname(__file__), "apollo_results.jsonl")
SEEN_FILE    = os.path.join(os.path.dirname(__file__), "apollo_seen.json")

# Apollo org IDs for frontier labs
LAB_ORG_IDS = {
    "OpenAI":         "5a9cc68aa6da98d95ff67048",
    "Anthropic":      "60b50b73a2cb6800f59961c4",
    "Google DeepMind":"57c4b74da6da98370bc9529f",
    "xAI":            "641d585ca69aef00012e9172",
    "Mistral AI":     "6473d15ec8ef57000109e945",
    "Cohere":         "604a2bcbf6e9e50001fbd89d",
    "Inflection AI":  "62279e921c1b8400a5e960a8",
    "Meta Platforms": "61eb9fe374918300016fd884",
}

# Well-known companies to skip (already established, not "new")
KNOWN_COMPANIES = {
    # Big tech & AI labs
    "perplexity", "anthropic", "openai", "deepmind", "google", "microsoft",
    "meta", "apple", "amazon", "nvidia", "mistral", "cohere", "inflection",
    "adept", "xai", "character.ai", "runway", "stability ai", "scale ai",
    "hugging face", "together ai", "groq", "cerebras", "ai2", "allen institute",
    # VCs & established startups
    "a16z", "sequoia", "benchmark", "greylock", "khosla ventures", "founders fund",
    # Large AI infra & tools (not stealth)
    "coreweave", "cognition", "cognition labs", "adobe", "luma ai", "luma labs",
    "poolside", "vanta", "midjourney", "elevenlabs", "eleven labs", "fixie",
    "repl.it", "replit", "cursor", "anysphere", "magic", "magic ai",
    # Universities & research institutes
    "stanford university", "stanford", "mit", "massachusetts institute of technology",
    "harvard university", "harvard", "cmu", "carnegie mellon", "uc berkeley", "berkeley",
    "university of washington", "university of toronto", "university of cambridge",
    "oxford university", "university of oxford", "inria", "eth zurich",
    # Misc false positives
    "yahoo", "twitter", "tesla", "spacex", "neuralink", "the boring company",
    " WAYE ", "databricks", "snowflake", "palantir", "anduril", "epic systems",
}

# Education keywords to skip
EDU_KEYWORDS = ["university", "college", "institute of technology", "school of ",
                "academy", "institute for ", "research center", "national laboratory"]

FOUNDER_TITLES = [
    "founder", "co-founder", "ceo", "chief executive officer",
    "founding engineer", "founding member", "founding researcher",
    "cofounder", "co founder",
]

def apollo_search(page=1):
    import http.client, ssl
    payload = json.dumps({
        "person_titles": FOUNDER_TITLES,
        "person_past_organization_ids": list(LAB_ORG_IDS.values()),
        "organization_keywords": ["stealth", "stealth startup", "stealth mode"],
        "person_locations": ["United States"],
        "per_page": 100,
        "page": page,
    }).encode()
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.apollo.io", context=ctx, timeout=30)
    conn.request("POST", "/api/v1/mixed_people/api_search", body=payload, headers={
        "Content-Type": "application/json",
        "X-Api-Key": APOLLO_KEY,
    })
    r = conn.getresponse()
    data = json.loads(r.read())
    conn.close()
    return data

def is_known_company(name):
    if not name:
        return True
    n = name.lower()
    # Check known company list
    if any(k in n for k in KNOWN_COMPANIES):
        return True
    # Check education keywords
    if any(k in n for k in EDU_KEYWORDS):
        return True
    return False

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def run():
    if not APOLLO_KEY:
        print("ERROR: APOLLO_API_KEY not set")
        return

    seen = load_seen()
    new_results = []

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Running Apollo search...")

    for page in range(1, 4):  # Up to 300 results (3 pages × 100)
        data = apollo_search(page=page)
        people = data.get("people", [])
        if not people:
            break

        for p in people:
            pid = p.get("id", "")
            if pid in seen:
                continue
            seen.add(pid)

            org = p.get("organization") or {}
            org_name = org.get("name", "")
            first_name = p.get("first_name", "")
            last_name_obs = p.get("last_name_obfuscated", "")
            title = p.get("title", "")
            linkedin = p.get("linkedin_url", "")
            city = p.get("city", "")
            state = p.get("state", "")

            # Skip known established companies
            if is_known_company(org_name):
                continue

            result = {
                "id": pid,
                "name": f"{first_name} {last_name_obs}".strip(),
                "first_name": first_name,
                "title": title,
                "company": org_name,
                "company_size": org.get("estimated_num_employees"),
                "company_industry": org.get("industry"),
                "company_website": org.get("website_url"),
                "location": f"{city}, {state}".strip(", "),
                "linkedin_url": linkedin,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            new_results.append(result)

        time.sleep(0.5)

    if new_results:
        with open(OUTPUT_FILE, "a") as f:
            for r in new_results:
                f.write(json.dumps(r) + "\n")
        print(f"\n✅ {len(new_results)} new leads saved\n")
        for r in new_results[:15]:
            print(f"  {r['name']} | {r['title'][:45]} @ {r['company']}")
            if r.get("linkedin_url"):
                print(f"    {r['linkedin_url']}")
    else:
        print("No new results.")

    save_seen(seen)

if __name__ == "__main__":
    run()
