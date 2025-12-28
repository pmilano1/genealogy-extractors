"""
Ancestry Record Extractor
Parses Ancestry.com search results (requires subscription)
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class AncestryExtractor(BaseRecordExtractor):
    """Extract records from Ancestry.com search results"""
    
    def __init__(self):
        super().__init__("Ancestry")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from Ancestry results
        
        Ancestry structure (varies by record type):
        <div class="recordCard" or similar>
          <a href="/...">Name</a>
          <div>Birth: YYYY Location</div>
          <div>Death: YYYY Location</div>
        </div>
        
        NOTE: Ancestry requires subscription and structure changes frequently
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []
        
        # Try multiple selectors for result cards
        result_items = (
            soup.find_all('div', class_=re.compile(r'recordCard|result|person', re.I)) or
            soup.find_all('li', class_=re.compile(r'result|record', re.I)) or
            soup.find_all('tr', class_=re.compile(r'result|record', re.I))
        )
        
        print(f"[DEBUG] Found {len(result_items)} result items in Ancestry HTML")
        
        for item in result_items[:20]:
            try:
                record = self._extract_person(item, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                print(f"[DEBUG] Failed to extract person: {e}")
                continue
        
        return records
    
    def _extract_person(self, element, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single Ancestry result"""
        
        # Extract name and URL
        link = element.find('a', href=True)
        if not link:
            return None
        
        name = link.get_text(strip=True)
        url = link.get('href', '')
        if url and not url.startswith('http'):
            url = f"https://www.ancestry.com{url}"
        
        # Extract birth year and place
        birth_year = None
        birth_place = None
        death_year = None
        
        text = element.get_text()
        
        # Look for birth info
        birth_match = re.search(r'Birth:?\s*(\d{4})\s*([^,\n]+)?', text, re.IGNORECASE)
        if birth_match:
            birth_year = int(birth_match.group(1))
            if birth_match.group(2):
                birth_place = birth_match.group(2).strip()
        
        # Look for death info
        death_match = re.search(r'Death:?\s*(\d{4})', text, re.IGNORECASE)
        if death_match:
            death_year = int(death_match.group(1))
        
        record = {
            'name': name,
            'birth_year': birth_year,
            'birth_place': birth_place,
            'death_year': death_year,
            'url': url,
            'source': self.source_name,
            'raw_data': {}
        }
        
        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

