# agents/feature_updater.py
"""
Agent 5: Feature Truth Auto-Updater & Topic Generator
Scrapes public marketing pages to detect new features or changes to existing features,
updates data/feature_truth.json, and generates new seed topics to avoid duplicates.
"""

import sys
import os
import json
import requests
from bs4 import BeautifulSoup

# Ensure we can import from the root directory when run directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import call_groq_with_retry, GROQ_MODEL, TEMPERATURE

TARGET_URLS = [
    "https://www.invohydra.com/",
    "https://www.invohydra.com/pricing",
    "https://www.invohydra.com/contact",
    "https://www.invohydra.com/products/smart-invoicing",
    "https://www.invohydra.com/products/smart-gst-billing",
    "https://www.invohydra.com/products/smart-proforma-invoice",
    "https://www.invohydra.com/products/pos-billing",
    "https://www.invohydra.com/products/smart-e-invoicing",
    "https://www.invohydra.com/products/smart-e-way-billing",
    "https://www.invohydra.com/products/smart-accounting",
    "https://www.invohydra.com/products/smart-inventory",
    "https://www.invohydra.com/products/multicurrency",
    "https://www.invohydra.com/Book"
]

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FEATURE_TRUTH_PATH = os.path.join(DATA_DIR, "feature_truth.json")
SEED_TOPICS_PATH = os.path.join(DATA_DIR, "seed_topics.json")

def scrape_urls(urls):
    """Scrapes all URLs and returns a combined text string of their content."""
    combined_text = ""
    for url in urls:
        print(f"🔍 Scraping: {url}")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer"]):
                script.extract()
                
            text = soup.get_text(separator=' ', strip=True)
            combined_text += f"\n\n--- Content from {url} ---\n{text}"
        except Exception as e:
            print(f"⚠️ Failed to scrape {url}: {e}")
            
    return combined_text

def analyze_features(website_text, current_features):
    """Uses Groq LLM to analyze website text against current features."""
    
    current_features_str = json.dumps(current_features, indent=2)
    
    system_prompt = (
        "You are InvoHydra's Product Analyst AI.\n"
        "Your task is to analyze the provided text scraped from our website and update our feature capability map.\n\n"
        f"Here is our current feature truth map:\n{current_features_str}\n\n"
        "Instructions:\n"
        "1. Read the website text carefully to identify any mentions of features.\n"
        "2. If a feature currently marked as `false` is now explicitly supported or advertised in the text, change it to `true`.\n"
        "3. If you discover entirely new major features advertised that are NOT in the current map, add them as new keys with value `true` (use snake_case for keys).\n"
        "4. Do NOT change a `true` feature to `false` unless the text explicitly states the feature has been deprecated or removed (which is rare). It's safer to leave `true` features as `true`.\n"
        "5. Return the EXHAUSTIVE updated feature map.\n\n"
        "Return your response EXCLUSIVELY as a valid JSON object matching the dictionary structure of the feature truth map (e.g. {\"feature_key\": true})."
    )
    
    truncated_text = website_text[:25000]
    
    user_payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Website Text:\n{truncated_text}"}
        ],
        "temperature": TEMPERATURE,
        "response_format": {"type": "json_object"}
    }
    
    print("🧠 Analyzing features with Groq LLM...")
    try:
        res_json = call_groq_with_retry(user_payload, timeout=90)
        result_content = res_json["choices"][0]["message"]["content"]
        return json.loads(result_content)
    except Exception as e:
        print(f"⚠️ Groq API request failed during feature analysis: {e}")
        return current_features

def generate_new_topics(current_features, existing_topics):
    """Generates 0-3 new seed topics that don't overlap with existing ones."""
    print("🧠 Checking for new seed topics to generate...")
    
    features_str = json.dumps(current_features, indent=2)
    topics_str = json.dumps(existing_topics, indent=2)
    
    system_prompt = (
        "You are InvoHydra's SEO Strategist AI.\n"
        "We need to generate high-level seed topics for our blog pipeline.\n\n"
        f"Our Product Features (Only promote 'true' features):\n{features_str}\n\n"
        f"Our HISTORICAL Seed Topics (Do NOT duplicate the meaning of these):\n{topics_str}\n\n"
        "Instructions:\n"
        "1. Based on our supported features, identify 0 to 3 completely NEW, broad, high-intent seed topics.\n"
        "2. Do NOT generate topics that overlap semantically with the historical topics.\n"
        "3. If our historical topics already thoroughly cover all our features, return an empty list [].\n"
        "4. Do NOT generate more than 3 topics.\n\n"
        "Return your response EXCLUSIVELY as a valid JSON object with a single key 'new_topics' containing a list of strings.\n"
        "Example: {\"new_topics\": [\"topic 1\", \"topic 2\"]}"
    )
    
    user_payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate new unique seed topics if needed."}
        ],
        "temperature": TEMPERATURE + 0.3, # Slightly higher temperature for creativity
        "response_format": {"type": "json_object"}
    }
    
    try:
        res_json = call_groq_with_retry(user_payload, timeout=90)
        result_content = res_json["choices"][0]["message"]["content"]
        result = json.loads(result_content)
        return result.get("new_topics", [])
    except Exception as e:
        print(f"⚠️ Groq API request failed during topic generation: {e}")
        return []

def main():
    print("🚀 Starting Feature Truth Auto-Updater & Topic Generator...")
    
    # 1. Load current feature truth and existing topics
    try:
        with open(FEATURE_TRUTH_PATH, "r", encoding="utf-8") as f:
            current_features = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load {FEATURE_TRUTH_PATH}: {e}")
        return
        
    try:
        with open(SEED_TOPICS_PATH, "r", encoding="utf-8") as f:
            existing_topics = json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load {SEED_TOPICS_PATH}. Starting with empty list.")
        existing_topics = []

    # 2. Scrape website
    website_text = scrape_urls(TARGET_URLS)
    if not website_text.strip():
        print("❌ No text scraped from URLs. Exiting.")
        return
        
    # 3. Analyze features with LLM
    updated_features = analyze_features(website_text, current_features)
    
    # 4. Save updated features
    if updated_features:
        try:
            with open(FEATURE_TRUTH_PATH, "w", encoding="utf-8") as f:
                json.dump(updated_features, f, indent=2)
            print(f"✅ Successfully updated {FEATURE_TRUTH_PATH}")
            
            changes = []
            for k, v in updated_features.items():
                if k not in current_features:
                    changes.append(f"  - [NEW] {k}: {v}")
                elif current_features[k] != v:
                    changes.append(f"  - [CHANGED] {k}: {current_features[k]} -> {v}")
                    
            if changes:
                print("Changes detected:")
                print("\n".join(changes))
            else:
                print("No changes detected in features.")
        except Exception as e:
            print(f"❌ Failed to save updated features: {e}")
            
    # 5. Generate new seed topics
    new_topics = generate_new_topics(updated_features or current_features, existing_topics)
    if new_topics:
        print(f"🌟 Generated {len(new_topics)} NEW seed topics:")
        for t in new_topics:
            print(f"  - {t}")
            
        existing_topics.extend(new_topics)
        try:
            with open(SEED_TOPICS_PATH, "w", encoding="utf-8") as f:
                json.dump(existing_topics, f, indent=2)
            print(f"✅ Successfully appended new topics to {SEED_TOPICS_PATH}")
        except Exception as e:
            print(f"❌ Failed to save new topics: {e}")
    else:
        print("✅ No new seed topics needed. Existing topics cover the features.")

if __name__ == "__main__":
    main()
