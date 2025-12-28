"""
MyHeritage Record Extractor
Parses MyHeritage search results (requires subscription)
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class MyHeritageExtractor(BaseRecordExtractor):
    """Extract records from MyHeritage search results"""
    
    def __init__(self):
        super().__init__("MyHeritage")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from MyHeritage results
        
        MyHeritage structure:
        <div class="result-item" or similar>
          <a href="/...">Name</a>
          <div>b. YYYY Location</div>
          <div>d. YYYY Location</div>
        </div>
        
        NOTE: MyHeritage requires subscription
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []
        
        # Try multiple selectors for result items
        result_items = (
            soup.find_all('div', class_=re.compile(r'result|item|person|record', re.I)) or
            soup.find_all('li', class_=re.compile(r'result|item', re.I)) or
            soup.find_all('tr', class_=re.compile(r'result|record', re.I))
        )
        
        print(f"[DEBUG] Found {len(result_items)} result items in MyHeritage HTML")
        
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
        """Extract data from a single MyHeritage result"""
        
        # Extract name and URL
        link = element.find('a', href=True)
        if not link:
            return None
        
        name = link.get_text(strip=True)
        url = link.get('href', '')
        if url and not url.startswith('http'):
            url = f"https://www.myheritage.com{url}"
        
        # Extract birth year and place
        birth_year = None
        birth_place = None
        death_year = None
        
        text = element.get_text()
        
        # Look for birth info (MyHeritage uses "b. YYYY")
        birth_match = re.search(r'b\.\s*(\d{4})\s*([^,\n]+)?', text, re.IGNORECASE)
        if birth_match:
            birth_year = int(birth_match.group(1))
            if birth_match.group(2):
                birth_place = birth_match.group(2).strip()
        
        # Look for death info (MyHeritage uses "d. YYYY")
        death_match = re.search(r'd\.\s*(\d{4})', text, re.IGNORECASE)
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

