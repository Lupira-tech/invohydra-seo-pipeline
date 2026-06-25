# inject_hyperlinks.py
import os
import json
import re
import requests
from config import GROQ_MODEL, TEMPERATURE, call_groq_with_retry

BLOGS_DIR = os.path.join("data", "blogs")

URL_MAPPING_INFO = """
- [InvoHydra](https://www.invohydra.com/) (Home/Platform)
- [Pricing](https://www.invohydra.com/pricing) (or Plan pricing)
- [Contact Us](https://www.invohydra.com/contact) (or scheduling/reaching support)
- [Smart Invoicing](https://www.invohydra.com/products/smart-invoicing)
- [Smart GST Billing](https://www.invohydra.com/products/smart-gst-billing)
- [Smart Proforma Invoice](https://www.invohydra.com/products/smart-proforma-invoice)
- [POS Billing](https://www.invohydra.com/products/pos-billing)
- [Smart E-Invoicing](https://www.invohydra.com/products/smart-e-invoicing) (exact URL: `https://www.invohydra.com/products/smart-e-invoicing`)
- [Smart E-Way Billing](https://www.invohydra.com/products/smart-e-way-billing) (exact URL: `https://www.invohydra.com/products/smart-e-way-billing`)
- [Smart Accounting](https://www.invohydra.com/products/smart-accounting)
- [Smart Inventory](https://www.invohydra.com/products/smart-inventory)
- [Multicurrency Billing](https://www.invohydra.com/products/multicurrency)
- [Book a Demo](https://www.invohydra.com/Book)
"""

import time

def inject_links_via_llm(markdown_content: str) -> str:
    system_prompt = (
        "You are an expert SEO copywriter. Your task is to update the provided blog post (written in Markdown) "
        "by naturally inserting hyperlinks into the text. Do NOT change the structure, headers, or rewrite the core content. "
        "Just identify existing words/phrases/features and turn them into appropriate markdown hyperlinks.\n\n"
        "HYPERLINK PLACEMENT RULES:\n"
        "1. Do not over-link. Only link when the feature, product, pricing, booking, or contact is mentioned. "
        "Limit to at most 1-2 links per major section.\n"
        "2. Ensure you use the exact matching URLs from this list:\n"
        f"{URL_MAPPING_INFO}\n"
        "3. Output ONLY the updated markdown content. Do not include any chat filler, intro, or explanation."
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": markdown_content}
        ],
        "temperature": 0.2
    }

    res_json = call_groq_with_retry(payload, timeout=60)
    return res_json["choices"][0]["message"]["content"].strip()

def main():
    if not os.path.exists(BLOGS_DIR):
        print(f"Directory {BLOGS_DIR} does not exist.")
        return

    files = os.listdir(BLOGS_DIR)
    print(f"Found {len(files)} files in {BLOGS_DIR} to process.")

    for filename in files:
        filepath = os.path.join(BLOGS_DIR, filename)
        if filename.endswith(".json"):
            print(f"Processing JSON blog: {filename}...")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    blog_data = json.load(f)
                
                markdown_body = blog_data.get("markdown_body", "")
                if markdown_body:
                    updated_body = inject_links_via_llm(markdown_body)
                    # Clean up potential LLM block wraps if it wraps with ```markdown
                    if updated_body.startswith("```markdown"):
                        updated_body = re.sub(r"^```markdown\n", "", updated_body)
                        updated_body = re.sub(r"\n```$", "", updated_body)
                    elif updated_body.startswith("```"):
                        updated_body = re.sub(r"^```\n", "", updated_body)
                        updated_body = re.sub(r"\n```$", "", updated_body)

                    blog_data["markdown_body"] = updated_body
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(blog_data, f, indent=2, ensure_ascii=False)
                    print(f"[OK] Updated {filename}")
                else:
                    print(f"[WARNING] No markdown_body found in {filename}")
            except Exception as e:
                print(f"[ERROR] Failed to process {filename}: {e}")
            time.sleep(3)

        elif filename.endswith(".md"):
            print(f"Processing MD blog: {filename}...")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                updated_content = inject_links_via_llm(content)
                if updated_content.startswith("```markdown"):
                    updated_content = re.sub(r"^```markdown\n", "", updated_content)
                    updated_content = re.sub(r"\n```$", "", updated_content)
                elif updated_content.startswith("```"):
                    updated_content = re.sub(r"^```\n", "", updated_content)
                    updated_content = re.sub(r"\n```$", "", updated_content)

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                print(f"[OK] Updated {filename}")
            except Exception as e:
                print(f"[ERROR] Failed to process {filename}: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
