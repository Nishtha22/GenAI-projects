"""
HTML parser to extract clean text.
"""

from bs4 import BeautifulSoup
from pathlib import Path
import re

class DocumentParser:
    """Parse HTML documents to clean text."""
    
    def parse_file(self, filepath: Path) -> dict:
        """Parse a single HTML file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # Extract source URL
        source_url = "unknown"
        source_match = re.search(r'<!-- SOURCE: (.+?) -->', html)
        if source_match:
            source_url = source_match.group(1)
        
        # Parse HTML
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove unwanted elements
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Get main content
        main = soup.find('main') or soup.find('article') or soup.body
        
        if not main:
            return None
        
        # Extract text
        text = main.get_text(separator='\n', strip=True)
        
        # Clean
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        return {
            'text': text.strip(),
            'source_url': source_url,
            'source_file': filepath.name
        }