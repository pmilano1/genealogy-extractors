"""
Antenati Record Extractor
Parses Antenati (Italian State Archives) NOMINATIVE search results

NOTE: Antenati has two search types:
1. Registry search (/search-registry/) - returns registry BOOKS (not used)
2. Nominative search (/search-nominative/) - returns individual PEOPLE (this extractor)
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class AntenatiExtractor(BaseRecordExtractor):
    """Extract individual person records from Antenati nominative search results"""

    def __init__(self):
        super().__init__("Antenati")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual person records from Antenati nominative search

        Structure:
        <div class="search-item" data-id="ID">
          <h3><a href="URL">SURNAME Given Name</a></h3>
          <div class="nominative-links">
            <span>Father: NAME</span>
            <span>Mother: NAME</span>
            <span>Spouse: NAME</span>
          </div>
          <div class="nominative-records">
            <a href="...">Birth: LOCATION YEAR</a>
            <a href="...">Marriage: LOCATION YEAR</a>
            <a href="...">Death: LOCATION YEAR</a>
          </div>
        </div>
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []

        # Find all person items (nominative search uses div.search-item)
        person_items = soup.find_all('div', class_='search-item')

        print(f"[DEBUG] Found {len(person_items)} people in Antenati nominative search")

        for item in person_items[:20]:  # Top 20 results
            try:
                record = self._extract_person(item, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                print(f"[DEBUG] Failed to extract person: {e}")
                continue

        return records
    
    def _extract_person(self, element, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single Antenati person record"""

        # Extract name from <h3><a>
        name_link = element.find('h3')
        if not name_link:
            return None

        name_link = name_link.find('a')
        if not name_link:
            return None

        name = name_link.get_text(strip=True)
        url = name_link.get('href', '')
        if url and not url.startswith('http'):
            url = f"https://antenati.cultura.gov.it{url}"

        # Extract birth year and location from nominative-records
        birth_year = None
        birth_place = None
        death_year = None

        records_div = element.find('div', class_='nominative-records')
        if records_div:
            # Look for birth record link
            birth_link = records_div.find('a', string=re.compile(r'Birth|Nascita', re.I))
            if birth_link:
                text = birth_link.get_text()
                # Extract year from "Birth: Location YEAR" or "Nascita: Location YEAR"
                year_match = re.search(r'\b(1[7-9]\d{2}|20\d{2})\b', text)
                if year_match:
                    birth_year = int(year_match.group(1))
                # Extract location (text before year)
                loc_match = re.search(r':\s*([^,]+)', text)
                if loc_match:
                    birth_place = loc_match.group(1).strip()

            # Look for death record
            death_link = records_div.find('a', string=re.compile(r'Death|Morte', re.I))
            if death_link:
                text = death_link.get_text()
                year_match = re.search(r'\b(1[7-9]\d{2}|20\d{2})\b', text)
                if year_match:
                    death_year = int(year_match.group(1))

        # Extract family relationships
        family = {}
        links_div = element.find('div', class_='nominative-links')
        if links_div:
            for span in links_div.find_all('span'):
                text = span.get_text(strip=True)
                if 'Father' in text or 'Padre' in text:
                    family['father'] = text.split(':', 1)[1].strip() if ':' in text else text
                elif 'Mother' in text or 'Madre' in text:
                    family['mother'] = text.split(':', 1)[1].strip() if ':' in text else text
                elif 'Spouse' in text or 'Coniuge' in text:
                    family['spouse'] = text.split(':', 1)[1].strip() if ':' in text else text

        # Use search params as fallback
        if not birth_place:
            birth_place = search_params.get('location')

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_place': birth_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'family': family
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if Antenati page has results"""
        indicators = [
            r'\d+\s+risultati',
            r'\d+\s+records?',
            'registry',
            'antenati.cultura.gov.it'
        ]
        
        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False

