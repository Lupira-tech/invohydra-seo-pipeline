# agents/illustrator.py
"""
Agent 7 (Phase 4.5): The Media Illustrator

Reads the generated blogs from Agent 4, uses the Gemini API to generate
interactive Mermaid.js flowcharts based on the blog's content, and optionally
attempts to generate a header image using Imagen 3.
It injects the charts directly into the Markdown body.
"""

import os
import sys
import json
import time

# Make the project root importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import google.generativeai as genai

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"))

BLOGS_DIR = os.path.join(_project_root, "data", "blogs")

def setup_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ GEMINI_API_KEY is missing. Illustrator cannot run.")
        return False
    genai.configure(api_key=api_key)
    return True

def generate_mermaid_chart(blog_title: str, blog_content: str) -> str:
    """Uses Gemini 1.5 Flash to generate a Mermaid.js chart based on the blog text."""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = (
            f"You are an expert technical illustrator for a B2B SaaS blog. "
            f"Read the following blog post titled '{blog_title}' and create ONE highly relevant, "
            f"professional Mermaid.js flowchart or architecture diagram that visualizes a key concept from the text.\n\n"
            f"Requirements:\n"
            f"1. Output ONLY the raw Mermaid code inside a markdown block (```mermaid ... ```).\n"
            f"2. Do not include any other text or explanations.\n"
            f"3. Make it detailed but clean.\n"
            f"4. CRITICAL: Every node text/label MUST be enclosed in double quotes to prevent syntax errors. For example: A[\"My Label (details)\"] instead of A[My Label (details)]. Do not use parentheses, brackets, colons, or slashes inside a node label unless the entire label is wrapped in double quotes.\n\n"
            f"Blog Content Preview:\n{blog_content[:3000]}"
        )
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up in case Gemini added extra markdown wrapping
        if text.startswith("```mermaid"):
            return text + "\n"
        elif text.startswith("```"):
            return text.replace("```", "```mermaid\n", 1) + "\n"
        else:
            return f"```mermaid\n{text}\n```\n"
    except Exception as e:
        print(f"   ⚠️ Gemini Mermaid Generation Failed: {e}")
        return ""

def illustrate_blogs():
    print("\n" + "═"*60)
    print("  🎨  PHASE 4.5 — AGENT 7: THE ILLUSTRATOR (GEMINI)")
    print("═"*60)

    if not setup_gemini():
        return

    if not os.path.exists(BLOGS_DIR):
        print(f"⚠️ No blogs found in {BLOGS_DIR}.")
        return

    blog_files = [f for f in os.listdir(BLOGS_DIR) if f.endswith('.json')]
    if not blog_files:
        print("⚠️ No JSON blog files found. Exiting.")
        return

    print(f"📄 Found {len(blog_files)} blogs to illustrate.")

    for idx, filename in enumerate(blog_files, 1):
        filepath = os.path.join(BLOGS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            blog_data = json.load(f)

        title = blog_data.get("meta_title", "Untitled")
        body = blog_data.get("markdown_body", "")

        # Skip if already illustrated to save API calls
        if "```mermaid" in body:
            print(f"⏩ [{idx}/{len(blog_files)}] '{title}' already has a chart. Skipping.")
            continue

        print(f"✨ [{idx}/{len(blog_files)}] Generating Gemini charts for: '{title}'...")
        
        mermaid_code = generate_mermaid_chart(title, body)
        
        if mermaid_code:
            # Inject the chart after the first or second paragraph
            paragraphs = body.split("\n\n")
            if len(paragraphs) > 2:
                paragraphs.insert(2, f"\n### Concept Visualization\n{mermaid_code}\n")
            else:
                paragraphs.append(f"\n### Concept Visualization\n{mermaid_code}\n")
                
            blog_data["markdown_body"] = "\n\n".join(paragraphs)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(blog_data, f, indent=2, ensure_ascii=False)
            print(f"   ✅ Successfully injected Mermaid chart into {filename}")
        else:
            print(f"   ❌ Failed to generate chart for {filename}")

        # Sleep to respect rate limits
        time.sleep(2)

    print("\n" + "═"*60)
    print("  ✅  ILLUSTRATION COMPLETE")
    print("═"*60)

if __name__ == "__main__":
    illustrate_blogs()
