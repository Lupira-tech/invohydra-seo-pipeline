# agents/discoverer.py
"""
Agent 1: The Keyword Discoverer.

Automatically finds new, relevant long-tail keywords based on a broad seed topic.

Pipeline:
  Seed Topic
      ↓
  Serper API — Primary search (transactional query)
      ↓
  If PAA=0 and Related=0 → Secondary search (informational variant)
      ↓
  Extract from: titles + snippets + sitelink titles (PAA/Related if available)
      ↓
  Groq LLM — filter junk, remove competitor brands, clean into keyword format
      ↓
  Clean list of 10-20 long-tail keywords
"""

import sys
import os

# Makes the project root importable when this file is run directly.
# e.g.  python agents/discoverer.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import requests
from typing import List, Dict, Any
from config import GROQ_MODEL, TEMPERATURE, call_groq_with_retry


# ──────────────────────────────────────────────────────────────────────────────
# HELPER: INFORMATIONAL QUERY VARIANT
# ──────────────────────────────────────────────────────────────────────────────

def _to_informational_query(seed_topic: str) -> str:
    """
    Generates a genuinely different informational query from any seed topic.
    Always produces a different string — never returns the same topic unchanged.

    Strips leading commercial words ("best", "top", "free") first so the
    secondary search is meaningfully different from the primary.

    Examples:
      "best GST billing software for Indian MSMEs"
        → "how to choose GST billing software for Indian MSMEs"
      "GST billing software for Indian MSMEs"
        → "how to choose GST billing software for Indian MSMEs"
      "how to automate invoicing for SaaS India"
        → "what is the best invoicing for SaaS India"
    """
    topic = seed_topic.strip()

    # Strip leading commercial/superlative words so we don't produce the same query
    strip_prefixes = ["best ", "top ", "free ", "cheap ", "cheapest ", "online "]
    topic_lower = topic.lower()
    for prefix in strip_prefixes:
        if topic_lower.startswith(prefix):
            topic = topic[len(prefix):]
            break

    # If already informational, rephrase differently
    informational_starters = ["how to", "what is", "why ", "when ", "which "]
    if any(topic.lower().startswith(s) for s in informational_starters):
        return f"what is the best {topic}"

    return f"how to choose {topic}"


# ──────────────────────────────────────────────────────────────────────────────
# HELPER: GOOGLE AUTOCOMPLETE
# ──────────────────────────────────────────────────────────────────────────────

def get_google_autocomplete(query: str) -> List[str]:
    """
    Fetches autocomplete suggestions from Google for the given query.
    This provides excellent long-tail keywords that real users are typing.
    """
    url = f"http://suggestqueries.google.com/complete/search?client=chrome&q={query}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if len(data) > 1 and isinstance(data[1], list):
            return data[1]
    except Exception as e:
        print(f"⚠️  Google Autocomplete failed: {e}")
    return []


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1: SEARCH GOOGLE VIA SERPER API
# ──────────────────────────────────────────────────────────────────────────────

def search_seed_topic(seed_topic: str) -> Dict[str, Any]:
    """
    Calls the Serper API (Google Search wrapper) for the given seed topic.
    Uses India geo-targeting (gl=in) for accurate GST/billing-related results.

    Returns the full Serper JSON response.
    """
    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        raise ValueError(
            "SERPER_API_KEY is not set. "
            "Sign up at https://serper.dev (2,500 free searches) and add it to your .env file."
        )

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": serper_key,
        "Content-Type": "application/json"
    }
    payload = {
        "q": seed_topic,
        "gl": "in",   # India geo-location — critical for GST/billing accuracy
        "hl": "en",
        "num": 10
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else "unknown"
        print(f"⚠️  Serper API HTTP error {status}: {e}")
        raise
    except requests.exceptions.Timeout:
        print("⚠️  Serper API timed out after 15s.")
        raise
    except requests.exceptions.ConnectionError:
        print("⚠️  Could not connect to Serper API. Check your internet connection.")
        raise


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2: EXTRACT KEYWORD CANDIDATES FROM SERPER RESPONSE
# ──────────────────────────────────────────────────────────────────────────────

def extract_keyword_candidates(serper_data: Dict[str, Any]) -> List[str]:
    """
    Extracts raw keyword candidates from a Serper API response.

    Extraction priority:
      1. 'People Also Ask'  — best long-tail signals (when available)
      2. 'Related Searches' — strong intent signals (when available)
      3. Organic titles     — always present, topic-rich
      4. Organic snippets   — always present, descriptive sentence fragments
         containing natural keyword phrases (e.g. "key factors to consider
         when choosing GST billing software for retail store")
      5. Sitelink titles    — sub-section headings from top-ranking pages,
         often expose specific sub-topics (e.g. "Benefits of Using Robust
         GST Billing Software")

    Note: On some Serper plans, PAA and Related Searches keys are absent
    entirely from the response. Sources 3-5 ensure we still get 15-25
    rich candidates regardless of plan tier.
    """
    candidates = []
    organic_items = serper_data.get("organic", [])

    # ── 1. People Also Ask (when available) ──────────────────────────────────
    paa_items = serper_data.get("peopleAlsoAsk", [])
    paa_questions = [
        item.get("question", "").strip()
        for item in paa_items
        if item.get("question", "").strip()
    ]
    print(f"   ├── 'People Also Ask' questions: {len(paa_questions)}")
    candidates.extend(paa_questions)

    # ── 2. Related Searches (when available) ─────────────────────────────────
    related_items = serper_data.get("relatedSearches", [])
    related_queries = [
        item.get("query", "").strip()
        for item in related_items
        if item.get("query", "").strip()
    ]
    print(f"   ├── 'Related Searches':           {len(related_queries)}")
    candidates.extend(related_queries)

    # ── 3. Organic titles (always present) ───────────────────────────────────
    # Page titles are hand-crafted for SEO — dense with target keyword phrases.
    organic_titles = [
        item.get("title", "").strip()
        for item in organic_items
        if item.get("title", "").strip() and len(item.get("title", "")) < 120
    ]
    print(f"   ├── Organic titles:               {len(organic_titles)}")
    candidates.extend(organic_titles)

    # ── 4. Organic snippets (always present) ─────────────────────────────────
    # Snippets are Google-selected excerpts — they contain natural language
    # descriptions of page content, rich with long-tail intent phrases.
    # The LLM extracts keyword intent from these even though they're sentences.
    organic_snippets = [
        item.get("snippet", "").strip()
        for item in organic_items
        if item.get("snippet", "").strip() and len(item.get("snippet", "")) < 400
    ]
    print(f"   ├── Organic snippets:             {len(organic_snippets)}")
    candidates.extend(organic_snippets)

    # ── 5. Sitelink titles (bonus sub-topic signals) ─────────────────────────
    # Sitelinks appear on top-ranking pages and expose specific sub-sections.
    # e.g. "## Benefits of Using Robust GST Billing Software" is a keyword goldmine.
    sitelink_titles = []
    for item in organic_items:
        for sitelink in item.get("sitelinks", []):
            title = sitelink.get("title", "").strip()
            # Strip markdown heading prefixes like "## " that Serper sometimes includes
            title = title.lstrip("#").strip()
            if title and len(title) < 120:
                sitelink_titles.append(title)
    print(f"   └── Sitelink sub-topic signals:   {len(sitelink_titles)}")
    candidates.extend(sitelink_titles)

    # ── Deduplicate while preserving insertion order ──────────────────────────
    seen = set()
    unique = []
    for c in candidates:
        normalized = c.lower().strip()
        if normalized not in seen and len(normalized) > 5:
            seen.add(normalized)
            unique.append(c)

    return unique


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3: FILTER AND CLEAN WITH GROQ LLM
# ──────────────────────────────────────────────────────────────────────────────

def filter_keywords_with_llm(candidates: List[str], seed_topic: str) -> List[str]:
    """
    Sends raw keyword candidates to Groq LLM for intelligent filtering.

    The LLM:
      - Reads titles, snippets, and sitelink headings as raw input
      - Extracts and rewrites them into clean 3-9 word keyword phrases
      - Removes competitor brand names (Zoho, Tally, QuickBooks, Vyapar, etc.)
      - Removes irrelevant or overly generic phrases
      - Returns 10-20 high-quality long-tail keywords

    Falls back to returning the top 15 raw candidates if the API fails.
    """


    system_prompt = (
        "You are an expert B2B SEO Keyword Analyst for InvoHydra — a GST billing, invoicing, "
        "and compliance SaaS platform built for Indian MSMEs and SaaS founders.\n\n"
        "You will receive raw text extracted from Google Search results. This includes page titles, "
        "meta snippets, and sitelink headings — not clean keywords yet. "
        "Your job is to read all of this raw text and extract/rewrite the best long-tail keyword phrases.\n\n"
        "STRICT FILTERING RULES:\n"
        "1. ✅ KEEP & REWRITE: Extract keyword intent from titles, snippets, and headings. "
        "Convert them into clean, concise search keyword format (lowercase, 3-9 words).\n"
        "   Example: 'Discover the 6 best GST Billing software in India for 2025. Compare features...'\n"
        "   → 'best gst billing software india 2025', 'gst billing software features comparison'\n"
        "2. ✅ KEEP: Long-tail keywords about GST billing, invoicing, tax compliance, "
        "recurring billing, GSTIN validation, or SaaS billing tools in India.\n"
        "3. ✅ KEEP: Real user questions or informational intents "
        "(e.g., 'how to set up gst billing software', 'features of gst billing software').\n"
        "4. ❌ REMOVE: Any competitor brand names — Zoho, Tally, TallyPrime, QuickBooks, Vyapar, "
        "ClearTax, FreshBooks, Khatabook, Marg, Busy, Biz Analyst, ProfitBooks, eR4u, "
        "Sleek Bill, Smaket, or any other named software product.\n"
        "5. ❌ REMOVE: Generic single-topic phrases under 3 words.\n"
        "6. ❌ REMOVE: Navigation phrases like 'navigate to downloads', 'FAQs view and download'.\n"
        "7. ❌ REMOVE: Phrases longer than 10 words.\n\n"
        "OUTPUT RULES:\n"
        "- Return between 10 and 20 keywords.\n"
        "- All keywords must be lowercase.\n"
        "- Return ONLY a valid JSON object with a single key 'keywords' (list of strings).\n"
        "- No explanations, no preamble, no markdown — pure JSON only.\n\n"
        "Example output:\n"
        "{\"keywords\": ["
        "\"gst billing software for msme india\", "
        "\"how to set up gst billing software\", "
        "\"key features of gst billing software\", "
        "\"gst compliant invoicing for small business\""
        "]}"
    )

    candidates_formatted = "\n".join(f"- {c}" for c in candidates)
    user_content = (
        f"Seed Topic: {seed_topic}\n\n"
        f"Raw text extracted from Google Search results ({len(candidates)} items):\n"
        f"{candidates_formatted}\n\n"
        f"Extract and return 10-20 high-quality long-tail keywords as a JSON object."
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": TEMPERATURE,
        "response_format": {"type": "json_object"}
    }

    try:
        res_json = call_groq_with_retry(payload, timeout=60)
        raw_content = res_json["choices"][0]["message"]["content"]
        parsed = json.loads(raw_content)
        keywords = parsed.get("keywords", [])

        if not keywords:
            print("⚠️  LLM returned empty keyword list. Using raw candidates as fallback.")
            return _fallback_clean(candidates)

        return keywords

    except Exception as e:
        print(f"⚠️  LLM error: {e}. Using fallback.")
        return _fallback_clean(candidates)


def _fallback_clean(candidates: List[str]) -> List[str]:
    """
    Fallback: returns top 15 raw candidates, lowercased and stripped.
    Used when the LLM call fails so the pipeline still progresses.
    """
    return [c.lower().strip() for c in candidates[:15] if len(c.strip()) > 5]


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────

def discover_keywords(seed_topic: str, output_path: str = None) -> List[str]:
    """
    Agent 1 main function.

    Takes a broad seed topic, runs one or two Serper searches, extracts
    candidate phrases from titles/snippets/sitelinks (plus PAA/Related if
    available), filters with Groq LLM, and returns 10-20 clean long-tail
    keywords ready for Agent 3 (Clusterer).

    Args:
        seed_topic:  e.g. "GST billing software for Indian MSMEs"
        output_path: Optional path to save keywords as JSON

    Returns:
        List of 10-20 clean, long-tail keyword strings.
    """
    print(f"\n{'─'*60}")
    print(f"🕵️   AGENT 1 — KEYWORD DISCOVERER")
    print(f"{'─'*60}")
    print(f"📌  Seed Topic: \"{seed_topic}\"")

    # ── Step 1: Primary search ─────────────────────────────────────────────
    print(f"\n[1/3] 🔍  Primary search via Serper API...")
    try:
        serper_data = search_seed_topic(seed_topic)
    except Exception as e:
        print(f"❌  Primary search failed — cannot proceed.\n    Error: {e}")
        return []

    candidates = extract_keyword_candidates(serper_data)

    # ── Step 1b: Secondary search if PAA and Related Searches were absent ──
    # On some Serper plans, these keys are missing entirely from the response.
    # We detect this and run a second search with an informational variant
    # to get a different set of organic titles/snippets as additional input.
    paa_present     = bool(serper_data.get("peopleAlsoAsk"))
    related_present = bool(serper_data.get("relatedSearches"))

    if not paa_present and not related_present:
        informational_query = _to_informational_query(seed_topic)

        # Only run secondary if it would actually be a different query
        if informational_query.lower() != seed_topic.lower():
            print(f"\n   ⚠️  PAA and Related Searches not available on this Serper plan.")
            print(f"   🔄  Running secondary search: \"{informational_query}\"")

            try:
                serper_data_2 = search_seed_topic(informational_query)
                candidates_2  = extract_keyword_candidates(serper_data_2)

                print(f"\n   ✅  Secondary search added {len(candidates_2)} new raw candidates.")

                # Merge, deduplicate, preserve order
                seen = set(c.lower().strip() for c in candidates)
                for c in candidates_2:
                    if c.lower().strip() not in seen:
                        candidates.append(c)
                        seen.add(c.lower().strip())

            except Exception as e:
                print(f"   ⚠️  Secondary search failed: {e}. Continuing with primary only.")
        else:
            print(f"\n   ℹ️  Secondary search skipped (same query as primary).")

    # ── Step 1c: Google Autocomplete (Bonus candidates) ────────────────────
    print(f"\n   🔍  Fetching Google Autocomplete suggestions...")
    autocomplete_candidates = get_google_autocomplete(seed_topic)
    if autocomplete_candidates:
        print(f"   ✅  Autocomplete found {len(autocomplete_candidates)} suggestions.")
        seen = set(c.lower().strip() for c in candidates)
        for c in autocomplete_candidates:
            if c.lower().strip() not in seen:
                candidates.append(c)
                seen.add(c.lower().strip())

    # ── Step 2: Summary ────────────────────────────────────────────────────
    print(f"\n[2/3] 📊  Total unique raw candidates: {len(candidates)}")

    if not candidates:
        print("⚠️  No candidates found. Try a different or broader seed topic.")
        return []

    # ── Step 3: LLM filtering ──────────────────────────────────────────────
    print(f"\n[3/3] 🧠  Filtering with Groq LLM (extracting keywords from raw text)...")
    keywords = filter_keywords_with_llm(candidates, seed_topic)

    # ── Print results ──────────────────────────────────────────────────────
    print(f"\n✅  Discovery complete — {len(keywords)} quality keywords found:")
    for i, kw in enumerate(keywords, 1):
        print(f"    {i:2}. {kw}")

    # ── Save output ────────────────────────────────────────────────────────
    if output_path and keywords:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(keywords, f, indent=2, ensure_ascii=False)
        print(f"\n💾  Keywords saved to: {output_path}")

    return keywords


# ──────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST MODE
# Run directly to test Agent 1 in isolation:
#   python agents/discoverer.py
#   python agents/discoverer.py "GST billing software for Indian MSMEs"
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    seed = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "GST billing software for Indian MSMEs"

    result = discover_keywords(
        seed_topic=seed,
        output_path="data/discovered_keywords.json"
    )

    print(f"\n🎉  Agent 1 standalone run complete.")
    print(f"    {len(result)} keywords ready for Agent 3 (Clusterer).")
