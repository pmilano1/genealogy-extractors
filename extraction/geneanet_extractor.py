"""
Geneanet Record Extractor
Parses Geneanet search results (French genealogy site)
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class GeneanetExtractor(BaseRecordExtractor):
    """Extract records from Geneanet search results"""
    
    def __init__(self):
        super().__init__("Geneanet")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual records from Geneanet results

        Geneanet structure:
        - Search results in <a class="ligne-resultat"> elements
        - Each has: name, birth/death dates, location, family tree link
        - URL pattern: https://gw.geneanet.org/...
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []

        # Find all result rows (ligne-resultat)
        result_items = soup.find_all('a', class_='ligne-resultat')

        print(f"[DEBUG] Found {len(result_items)} ligne-resultat items in Geneanet HTML")

        for item in result_items[:20]:  # Limit to first 20 results
            try:
                record = self._extract_individual(item, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                print(f"[DEBUG] Failed to extract individual: {e}")
                continue

        return records
    
    def _extract_individual(self, element, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single Geneanet individual

        Structure:
        <a class="ligne-resultat" href="URL">
          <div class="info-resultat">
            <div class="content-individu">
              <p class="text-large">SURNAME Given_Name</p>
              <p>Spouse: NAME (YEAR)</p>
            </div>
            <div class="content-periode">
              <p><span class="text-light">Birth</span> <span class="text-large">YEAR</span></p>
              <p><span class="text-light">Death</span> <span class="text-large">YEAR</span></p>
            </div>
            <div class="content-lieu">
              <p><span class="title-lieu">LOCATION</span></p>
            </div>
          </div>
        </a>
        """

        # Extract URL (element itself is the <a> tag)
        url = element.get('href', '')
        if not url:
            return None

        # Extract name from content-individu section
        name = ""
        name_elem = element.find('p', class_='text-large')
        if name_elem:
            # Clean up extra whitespace between surname and given name
            name = ' '.join(name_elem.get_text(strip=True).split())

        # Extract birth and death years from content-periode section
        birth_year = None
        death_year = None
        periode_div = element.find('div', class_='content-periode')
        if periode_div:
            # Find Birth year
            birth_p = periode_div.find('span', string='Birth')
            if birth_p and birth_p.parent:
                year_span = birth_p.parent.find('span', class_='text-large')
                if year_span:
                    try:
                        birth_year = int(year_span.get_text(strip=True))
                    except ValueError:
                        pass

            # Find Death year
            death_p = periode_div.find('span', string='Death')
            if death_p and death_p.parent:
                year_span = death_p.parent.find('span', class_='text-large')
                if year_span:
                    try:
                        death_year = int(year_span.get_text(strip=True))
                    except ValueError:
                        pass

        # Extract location from content-lieu section
        birth_place = None
        lieu_div = element.find('div', class_='content-lieu')
        if lieu_div:
            lieu_span = lieu_div.find('span', class_='title-lieu')
            if lieu_span:
                birth_place = lieu_span.get_text(strip=True)

        # Extract spouse info if present
        spouse = None
        spouse_p = element.find('span', string='Spouse')
        if spouse_p and spouse_p.parent:
            spouse_span = spouse_p.parent.find('span', class_='text-large')
            if spouse_span:
                spouse = spouse_span.get_text(strip=True)

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_place': birth_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'spouse': spouse
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if Geneanet page has results"""
        indicators = [
            r'\d+\s+résultats?',
            r'\d+\s+results?',
            '/individu/',
            'search results'
        ]
        
        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False

