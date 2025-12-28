"""
FreeBMD Record Extractor
Parses FreeBMD (UK Birth, Marriage, Death records) search results
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class FreeBMDExtractor(BaseRecordExtractor):
    """Extract records from FreeBMD search results"""
    
    def __init__(self):
        super().__init__("FreeBMD")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract BMD records from FreeBMD results
        
        FreeBMD structure:
        - Search results in table format
        - Columns: Surname, First name(s), District, Volume, Page, Quarter, Year
        - No direct URLs to individual records (just search results)
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []
        
        # Find results table
        table = soup.find('table', class_=re.compile(r'results?|data'))
        if not table:
            table = soup.find('table')
        
        if not table:
            return []
        
        # Extract rows (skip header)
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows[:20]:  # Top 20 results
            try:
                record = self._extract_row(row, search_params)
                if record:
                    records.append(record)
            except Exception:
                continue
        
        return records
    
    def _extract_row(self, row, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single FreeBMD table row"""
        
        cells = row.find_all('td')
        if len(cells) < 5:
            return None
        
        # FreeBMD columns: Surname, First name(s), District, Volume, Page, Quarter, Year
        surname = cells[0].get_text(strip=True)
        given_name = cells[1].get_text(strip=True)
        district = cells[2].get_text(strip=True) if len(cells) > 2 else None
        year = cells[-1].get_text(strip=True) if len(cells) > 6 else None
        
        # Build name
        name = f"{given_name} {surname}".strip()
        
        # Extract year
        birth_year = None
        if year:
            year_match = re.search(r'\b(1[7-9]\d{2}|20\d{2})\b', year)
            if year_match:
                birth_year = int(year_match.group(1))
        
        # FreeBMD doesn't have direct record URLs, use search URL
        url = search_params.get('url', 'https://www.freebmd.org.uk/')
        
        record = {
            'name': name,
            'birth_year': birth_year,
            'birth_place': district,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'district': district,
                'surname': surname,
                'given_name': given_name
            }
        }
        
        record['match_score'] = self.calculate_match_score(record, search_params)
        return record
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if FreeBMD page has results"""
        indicators = [
            r'\d+\s+results?',
            r'<table',
            'District',
            'Volume'
        ]
        
        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False

