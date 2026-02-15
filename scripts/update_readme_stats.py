#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import re

# Configuration
STATS_URL = os.getenv("ATTESTGRID_STATS_URL", "https://veridict.matrix.jp/v1/stats")
README_PATH = "README.md"

def fetch_stats():
    print(f"Fetching stats from {STATS_URL}...")
    try:
        with urllib.request.urlopen(STATS_URL) as response:
            if response.status != 200:
                print(f"Error: Status {response.status}")
                sys.exit(1)
            data = json.loads(response.read().decode())
            return data
    except Exception as e:
        print(f"Failed to fetch stats: {e}")
        sys.exit(1)

def format_block(stats):
    total = stats.get("receipts_total", 0)
    verify = stats.get("verify_total", 0)
    blocked = stats.get("passed_false", 0)
    rate = stats.get("passed_false_rate", 0.0)
    
    # Format with bold markdown
    return f"""<!-- ATTESTGRID_STATS_START -->
**Live stats (auto-updated):**
- Total Receipts: **{total}**
- Verifications: **{verify}**
- Blocked (passed:false): **{blocked}**
- Block rate: **{rate:.3f}**
<!-- ATTESTGRID_STATS_END -->"""

def update_readme(new_block):
    if not os.path.exists(README_PATH):
        print(f"Error: {README_PATH} not found.")
        sys.exit(1)
        
    with open(README_PATH, "r") as f:
        content = f.read()
        
    # Regex to replace the block
    pattern = re.compile(
        r"<!-- ATTESTGRID_STATS_START -->.*?<!-- ATTESTGRID_STATS_END -->",
        re.DOTALL
    )
    
    if not pattern.search(content):
        print("Error: Stats block markers not found in README.md")
        sys.exit(1)
        
    new_content = pattern.sub(new_block, content)
    
    if new_content == content:
        print("No changes needed.")
    else:
        with open(README_PATH, "w") as f:
            f.write(new_content)
        print("README.md updated successfully.")

def main():
    stats = fetch_stats()
    block = format_block(stats)
    update_readme(block)

if __name__ == "__main__":
    main()
