# main.py
"""
Main execution script for the InvoHydra SEO Pipeline.

Current agent flow:
  Agent 1 (Keyword Discoverer)  ← NEW
      ↓
  Agent 3 (Semantic Clusterer)
      ↓
  Agent 4 (Blog Writer)

Agent 2 (Difficulty Analyst) and Agent 5 (Auto-Publisher) are pending implementation.
"""

import os
import json
from agents.discoverer import discover_keywords
from agents.planner import load_keywords, load_feature_truth, cluster_keywords
from agents.writer import generate_all_blogs
from config import SEED_TOPICS

# ──────────────────────────────────────────────────────────────────────────────
# PIPELINE CONFIGURATION
# Edit these paths to match your project layout.
# ──────────────────────────────────────────────────────────────────────────────
MANUAL_KEYWORDS_PATH    = "data/manual_keywords.json"
DISCOVERED_KEYWORDS_PATH = "data/discovered_keywords.json"
FEATURES_PATH           = "data/feature_truth.json"
CLUSTERS_OUTPUT_PATH    = "data/clustered_keywords.json"
BLOGS_DIR               = "data/blogs"

# Set to True to skip Agent 1 and use manual_keywords.json instead
USE_MANUAL_KEYWORDS = False
# ──────────────────────────────────────────────────────────────────────────────


def run_agent_1() -> list:
    """
    Runs Agent 1 across all configured SEED_TOPICS.
    Deduplicates keywords across topics and saves to DISCOVERED_KEYWORDS_PATH.
    Returns the combined keyword list.
    """
    print("\n" + "═"*60)
    print("  PHASE 1 — AGENT 1: KEYWORD DISCOVERER")
    print("═"*60)
    print(f"  Seed topics configured: {len(SEED_TOPICS)}")
    for i, topic in enumerate(SEED_TOPICS, 1):
        print(f"  {i}. {topic}")

    all_discovered = []

    for seed in SEED_TOPICS:
        discovered = discover_keywords(seed_topic=seed)
        all_discovered.extend(discovered)

    # Deduplicate across all seed topics while preserving order
    seen = set()
    unique_keywords = []
    for kw in all_discovered:
        normalized = kw.lower().strip()
        if normalized not in seen:
            seen.add(normalized)
            unique_keywords.append(kw)

    print(f"\n📊  Combined total across {len(SEED_TOPICS)} seed topics: {len(unique_keywords)} unique keywords")

    if unique_keywords:
        os.makedirs("data", exist_ok=True)
        with open(DISCOVERED_KEYWORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(unique_keywords, f, indent=2, ensure_ascii=False)
        print(f"💾  All discovered keywords saved to: {DISCOVERED_KEYWORDS_PATH}")

    return unique_keywords


def run_agent_3(keywords: list) -> dict:
    """
    Runs Agent 3: clusters keywords against the feature truth map.
    Saves output to CLUSTERS_OUTPUT_PATH.
    """
    print("\n" + "═"*60)
    print("  PHASE 2 — AGENT 3: SEMANTIC INTENT CLUSTERER")
    print("═"*60)

    print(f"📦  Loading feature capabilities map from: {FEATURES_PATH}")
    features = load_feature_truth(FEATURES_PATH)

    print(f"🧠  Clustering {len(keywords)} keywords against feature truth map...")
    results = cluster_keywords(keywords, features)

    os.makedirs("data", exist_ok=True)
    with open(CLUSTERS_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    cluster_count  = len(results.get("clusters", []))
    rejected_count = len(results.get("rejected_keywords", []))
    print(f"✅  Clustered into {cluster_count} topic clusters.")
    print(f"🚫  Rejected {rejected_count} keywords (capability violations).")
    print(f"💾  Saved to: {CLUSTERS_OUTPUT_PATH}")

    return results


def run_agent_4() -> None:
    """Runs Agent 4: generates one blog post per cluster."""
    print("\n" + "═"*60)
    print("  PHASE 3 — AGENT 4: BLOG WRITER")
    print("═"*60)
    generate_all_blogs(CLUSTERS_OUTPUT_PATH, BLOGS_DIR)


def main():
    print("\n🚀  Starting InvoHydra SEO Pipeline...")

    # ── Phase 1: Keyword Discovery (Agent 1) ──────────────────────────────
    if USE_MANUAL_KEYWORDS:
        print(f"\n📦  USE_MANUAL_KEYWORDS=True — Loading from: {MANUAL_KEYWORDS_PATH}")
        keywords = load_keywords(MANUAL_KEYWORDS_PATH)
        print(f"✅  Loaded {len(keywords)} manual keywords.")
    else:
        keywords = run_agent_1()

        if not keywords:
            # Graceful fallback if all Serper searches failed
            print(
                f"\n⚠️  Agent 1 returned no keywords. "
                f"Falling back to manual keywords at: {MANUAL_KEYWORDS_PATH}"
            )
            keywords = load_keywords(MANUAL_KEYWORDS_PATH)
            print(f"✅  Fallback loaded {len(keywords)} keywords.")

    # ── Phase 2: Semantic Clustering (Agent 3) ────────────────────────────
    run_agent_3(keywords)

    # ── Phase 3: Blog Generation (Agent 4) ───────────────────────────────
    run_agent_4()

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "═"*60)
    print("  🎉  PIPELINE RUN COMPLETE")
    print("═"*60)
    print(f"  ├── Discovered keywords → {DISCOVERED_KEYWORDS_PATH}")
    print(f"  ├── Clustered keywords  → {CLUSTERS_OUTPUT_PATH}")
    print(f"  └── Blog posts          → {BLOGS_DIR}/")
    print("═"*60)
    print("\nNext steps:")
    print("  • Review blogs:     python serve_blogs.py")
    print("  • Inject links:     python inject_hyperlinks.py")
    print("  • View discovered:  data/discovered_keywords.json\n")


if __name__ == "__main__":
    main()
