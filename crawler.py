import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

def crawl_page(url, domain):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        content = "\n".join(lines)

        # Remove URLs that don't belong to the owner's domain
        content = re.sub(r'https?://(?!' + re.escape(domain) + r')\S+', '', content)
        content = re.sub(r'www\.(?!' + re.escape(domain) + r')\S+', '', content)

        return content
    except Exception as e:
        print(f"Crawl failed for {url}: {e}")
        return ""

def get_internal_links(url, domain):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        links = set()
        for a in soup.find_all('a', href=True):
            href = urljoin(url, a['href'])
            parsed = urlparse(href)
            if parsed.netloc == domain and parsed.scheme in ('http', 'https'):
                clean = parsed.scheme + "://" + parsed.netloc + parsed.path
                links.add(clean)
        return links
    except Exception as e:
        print(f"Failed to get links from {url}: {e}")
        return set()

def crawl_website(url, max_pages=10, additional_urls=None):
    domain = urlparse(url).netloc
    visited = set()
    all_content = []

    # Try sitemap first
    sitemap_urls = get_sitemap_urls(url)
    if sitemap_urls:
        queue = sitemap_urls
    else:
        queue = [url]

    # Add manually specified URLs
    if additional_urls:
        queue = additional_urls + queue

    while queue and len(visited) < max_pages:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        content = crawl_page(current, domain)
        if content:
            all_content.append(f"--- {current} ---\n{content}")

        if not sitemap_urls:
            new_links = get_internal_links(current, domain)
            for link in new_links:
                if link not in visited:
                    queue.append(link)

    combined = "\n\n".join(all_content)
    return combined[:3000]

def get_sitemap_urls(base_url):
    try:
        sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "xml")
            urls = [loc.text for loc in soup.find_all("loc")]
            return urls
    except Exception as e:
        print(f"Sitemap fetch failed: {e}")
    return []