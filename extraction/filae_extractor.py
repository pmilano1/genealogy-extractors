"""
Filae Record Extractor
Parses Filae.com French genealogy records
"""

import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base_extractor import BaseRecordExtractor


class FilaeExtractor(BaseRecordExtractor):
    """Extract records from Filae search results"""
    
    def __init__(self):
        super().__init__("Filae")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from Filae results
        
        Filae structure (French genealogy site):
        - Results in <div class="result-item"> or similar containers
        - Each result has name, dates, location, document type
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []
        
        # Try multiple selectors - Filae may use different structures
        result_items = (
            soup.find_all('div', class_=re.compile(r'result|record|item', re.I)) or
            soup.find_all('tr', class_=re.compile(r'result|record', re.I)) or
            soup.find_all('li', class_=re.compile(r'result|record', re.I)) or
            soup.find_all('article', class_=re.compile(r'result|record', re.I))
        )
        
        print(f"[DEBUG] Found {len(result_items)} result items in Filae HTML")
        
        for item in result_items[:20]:
            try:
                record = self._extract_person(item, search_params)
                if record and record.get('name'):
                    records.append(record)
            except Exception as e:
                print(f"[DEBUG] Filae extraction error: {e}")
                continue
        
        return records
    
    def _extract_person(self, item, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single Filae result"""
        
        # Try to find name
        name = None
        name_elem = (
            item.find(class_=re.compile(r'name|nom|person', re.I)) or
            item.find('a') or
            item.find('strong') or
            item.find('h3') or
            item.find('h4')
        )
        if name_elem:
            name = name_elem.get_text(strip=True)
        
        if not name:
            return None
        
        # Try to find birth year
        birth_year = None
        text = item.get_text()
        year_match = re.search(r'\b(1[7-9]\d{2}|20[0-2]\d)\b', text)
        if year_match:
            birth_year = int(year_match.group(1))
        
        # Try to find location
        location = None
        location_elem = item.find(class_=re.compile(r'place|lieu|location|ville', re.I))
        if location_elem:
            location = location_elem.get_text(strip=True)
        
        # Try to find URL
        url = None
        link = item.find('a', href=True)
        if link:
            href = link['href']
            if not href.startswith('http'):
                url = f"https://www.filae.com{href}"
            else:
                url = href
        
        # Try to find document type
        doc_type = None
        doc_elem = item.find(class_=re.compile(r'type|document|source', re.I))
        if doc_elem:
            doc_type = doc_elem.get_text(strip=True)
        
        record = {
            'name': name,
            'birth_year': birth_year,
            'birth_place': location,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'document_type': doc_type
            }
        }
        
        record['match_score'] = self.calculate_match_score(record, search_params)
        return record
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if Filae page has results"""
        soup = BeautifulSoup(content, 'html.parser')
        
        # Check for result count or result items
        result_count = soup.find(class_=re.compile(r'result.*count|nombre.*result', re.I))
        if result_count:
            text = result_count.get_text()
            if re.search(r'\d+', text):
                return True
        
        # Check for result containers
        results = soup.find_all(class_=re.compile(r'result|record', re.I))
        return len(results) > 0

