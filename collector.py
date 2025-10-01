import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re

URL = "https://ourworldindata.org/marriages-and-divorces"
OUT = Path("data/raw_blob.txt")

def extract_clean_content(url=URL):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    
    unwanted_tags = ["script", "style", "nav", "header", "footer", "aside", 
                    "iframe", "noscript", "meta", "link", "button", "form"]
    
    for tag in unwanted_tags:
        for element in soup.find_all(tag):
            element.decompose()
    
    unwanted_selectors = [
        ".site-header", ".site-footer", ".sidebar", ".navigation", ".breadcrumbs",
        ".share-buttons", ".social-buttons", ".newsletter", ".donate-button", 
        ".cookie-notice", ".popup", ".modal", ".advertisement", ".ad"
    ]
    
    for selector in unwanted_selectors:
        for element in soup.select(selector):
            element.decompose()
    
    main_content = None
    for selector in ["main", "article", ".content", ".post-content", ".entry-content"]:
        main_content = soup.select_one(selector)
        if main_content and len(main_content.get_text(strip=True)) > 1000:
            break
    
    if not main_content:
        main_content = soup.find("body")
    
    if not main_content:
        raise ValueError("Could not find main content")
    
    text = main_content.get_text(separator="\n", strip=True)
    
    lines = text.split("\n")
    clean_lines = []
    
    skip_phrases = ["menu", "search", "home", "about", "contact", "donate", 
                   "twitter", "facebook", "share", "embed", "download"]
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 15:
            continue
            
        if any(phrase in line.lower() for phrase in skip_phrases):
            continue
            
        if re.match(r'^[\d\s\-–,\.%\(\)\[\]]+$', line):
            continue
            
        clean_lines.append(line)
    
    clean_text = "\n\n".join(clean_lines)
    
    # Final cleanup
    clean_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', clean_text)
    clean_text = re.sub(r'[ \t]+', ' ', clean_text)
    clean_text = re.sub(r'\s*\[\d+\]\s*', ' ', clean_text)  # Remove citations
    
    return clean_text.strip()

if __name__ == "__main__":
    clean_content = extract_clean_content()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(clean_content, encoding="utf-8")
    print(f"Clean content saved to: {OUT.resolve()}")
    print(f"Content length: {len(clean_content):,} characters")