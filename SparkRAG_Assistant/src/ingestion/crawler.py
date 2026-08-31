"""
Simple web crawler for documentation.
"""

import httpx
from bs4 import BeautifulSoup
from pathlib import Path
import time
from tqdm import tqdm

class DocumentCrawler:
    """Crawl documentation websites."""
    
    def __init__(self, base_url: str, max_pages: int = 100, rate_limit: float = 1.0):
        self.base_url = base_url
        self.max_pages = max_pages
        self.rate_limit = rate_limit
        self.visited = set()
    
    def fetch_page(self, url: str) -> str:
        """Fetch a single page."""
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
        return ""
    
    def extract_links(self, html: str, base_url: str) -> list:
        """Extract documentation links."""
        soup = BeautifulSoup(html, 'lxml')
        links = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            
            # Make absolute URL
            if href.startswith('/'):
                href = base_url.rstrip('/') + href
            elif not href.startswith('http'):
                continue
            
            # Only documentation pages
            if base_url in href and href not in self.visited:
                links.append(href)
        
        return links
    
    def crawl(self, output_dir: Path) -> list:
        """Crawl and save pages."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        to_visit = [self.base_url]
        saved_files = []
        
        pbar = tqdm(total=self.max_pages, desc="Crawling")
        
        while to_visit and len(self.visited) < self.max_pages:
            url = to_visit.pop(0)
            
            if url in self.visited:
                continue
            
            self.visited.add(url)
            
            # Fetch
            html = self.fetch_page(url)
            if not html:
                continue
            
            # Save
            filename = f"page_{len(saved_files):04d}.html"
            filepath = output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"<!-- SOURCE: {url} -->\n")
                f.write(html)
            
            saved_files.append(filepath)
            pbar.update(1)
            
            # Extract links
            new_links = self.extract_links(html, self.base_url)
            to_visit.extend(new_links)
            
            # Rate limit
            time.sleep(self.rate_limit)
        
        pbar.close()
        return saved_files