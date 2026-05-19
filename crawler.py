import requests
from bs4 import BeautifulSoup

def crawl_website(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove junk
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines)

        # Trim to avoid overwhelming the AI
        return content[:5000]
    except Exception as e:
        print(f"Crawl failed: {e}")
        return ""