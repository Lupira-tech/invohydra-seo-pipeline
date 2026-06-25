import os, json

BLOGS_DIR = "data/blogs"

for filename in os.listdir(BLOGS_DIR):
    if filename.endswith(".json"):
        filepath = os.path.join(BLOGS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        body = data.get("markdown_body", "")
        
        # Strip everything before the first "# " (Title) to remove all old images and captions
        if "# " in body:
            body = "# " + body.split("# ", 1)[1]
            
        # Strip Mermaid charts
        if "```mermaid" in body:
            parts = body.split("```mermaid")
            new_body = parts[0]
            for part in parts[1:]:
                # Split at the end of the mermaid block
                if "```" in part:
                    new_body += part.split("```", 1)[1]
                else:
                    new_body += part
            body = new_body
            
        # Clean up empty Concept Visualization headers
        body = body.replace("### Concept Visualization\n\n", "")
            
        data["markdown_body"] = body
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

print("Scrubbed all blogs.")
