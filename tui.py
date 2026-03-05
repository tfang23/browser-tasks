#!/usr/bin/env python3
"""
tui.py - Display departure radar results in a terminal UI using rich.
"""
import json, os, sys
from datetime import datetime, timezone, timedelta

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.jsonl")
APOLLO_FILE  = os.path.join(os.path.dirname(__file__), "apollo_results.jsonl")

def load_results(hours=168):  # 7 days default
    if not os.path.exists(RESULTS_FILE):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    seen_authors = set()
    with open(RESULTS_FILE) as f:
        for line in f:
            try:
                r = json.loads(line)
                fetched = datetime.fromisoformat(r["fetched_at"])
                if fetched >= cutoff:
                    username = r["author"].get("username", "")
                    if username not in seen_authors:
                        seen_authors.add(username)
                        results.append(r)
            except:
                pass
    return sorted(results, key=lambda x: x["score"], reverse=True)

def load_apollo(hours=168):
    if not os.path.exists(APOLLO_FILE):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results, seen = [], set()
    with open(APOLLO_FILE) as f:
        for line in f:
            try:
                r = json.loads(line)
                fetched = datetime.fromisoformat(r["fetched_at"])
                pid = r["id"]
                if fetched >= cutoff and pid not in seen:
                    seen.add(pid)
                    results.append(r)
            except:
                pass
    return sorted(results, key=lambda x: x.get("company",""))

def run():
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text
        from rich import box
        HAS_RICH = True
    except ImportError:
        HAS_RICH = False

    twitter_results = load_results()
    apollo_results  = load_apollo()

    if not twitter_results and not apollo_results:
        print("No results found. Run monitor.py / apollo_monitor.py first.")
        sys.exit(0)

    if HAS_RICH:
        console = Console()

        # ── Twitter table ─────────────────────────────────────────────────────
        if twitter_results:
            t_table = Table(
                title=f"🐦 Twitter Signals  ·  {len(twitter_results)} result(s)",
                box=box.ROUNDED, show_lines=True,
                header_style="bold cyan", title_style="bold white", min_width=100,
            )
            t_table.add_column("#",        style="dim",        width=3,  justify="right")
            t_table.add_column("Handle",   style="bold yellow",width=18)
            t_table.add_column("Followers",                    width=10, justify="right")
            t_table.add_column("Score",                        width=7,  justify="center")
            t_table.add_column("Bio",      style="dim",        width=28)
            t_table.add_column("Tweet",                        width=55)
            t_table.add_column("Link",     style="blue",       width=14)

            for i, r in enumerate(twitter_results, 1):
                a     = r["author"]
                score = r["score"]
                t_table.add_row(
                    str(i),
                    f"@{a.get('username','?')}",
                    f"{(a.get('followers') or 0):,}",
                    Text(str(score), style="green" if score>=8 else "yellow" if score>=5 else "white"),
                    (a.get("bio") or "")[:80],
                    r["text"][:250],
                    f"t.co/{r['id'][-6:]}",
                )
            console.print()
            console.print(t_table)

        # ── Apollo table ──────────────────────────────────────────────────────
        if apollo_results:
            a_table = Table(
                title=f"🔭 Apollo — Stealth Founders w/ Lab Background  ·  {len(apollo_results)} result(s)",
                box=box.ROUNDED, show_lines=True,
                header_style="bold magenta", title_style="bold white", min_width=100,
            )
            a_table.add_column("#",        style="dim",         width=3,  justify="right")
            a_table.add_column("Name",     style="bold yellow", width=22)
            a_table.add_column("Title",    style="dim",         width=30)
            a_table.add_column("Company",  style="bold green",  width=28)
            a_table.add_column("Location",                      width=20)
            a_table.add_column("LinkedIn", style="blue",        width=16)

            for i, r in enumerate(apollo_results, 1):
                linkedin = r.get("linkedin_url","")
                handle = linkedin.split("/in/")[-1].rstrip("/") if "/in/" in linkedin else ""
                a_table.add_row(
                    str(i),
                    r.get("name","?"),
                    (r.get("title") or "")[:45],
                    r.get("company","?"),
                    r.get("location","")[:20],
                    handle[:16] if handle else "—",
                )
            console.print()
            console.print(a_table)

        console.print()
        console.print("[dim]Full data in results.jsonl / apollo_results.jsonl[/dim]")
        console.print()

    else:
        # Plain text fallback
        if twitter_results:
            print(f"\n{'='*80}\n  Twitter — {len(twitter_results)} signal(s)\n{'='*80}\n")
            for i, r in enumerate(twitter_results, 1):
                a = r["author"]
                print(f"[{i}] @{a.get('username')} | {a.get('followers',0):,} followers | score:{r['score']}")
                if a.get("bio"): print(f"    {a['bio'][:100]}")
                print(f"    {r['text'][:240]}")
                print(f"    {r['url']}")
                print()

        if apollo_results:
            print(f"\n{'='*80}\n  Apollo — {len(apollo_results)} stealth founder lead(s)\n{'='*80}\n")
            for i, r in enumerate(apollo_results, 1):
                print(f"[{i}] {r.get('name')} | {r.get('title','')[:45]} @ {r.get('company','?')}")
                if r.get("location"): print(f"    {r['location']}")
                if r.get("linkedin_url"): print(f"    {r['linkedin_url']}")
                print()

if __name__ == "__main__":
    run()
