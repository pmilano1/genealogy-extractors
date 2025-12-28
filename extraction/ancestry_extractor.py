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

        Ancestry structure:
        <div class="global-results-card">
          <table class="table tableHorizontal">
            <tr><th>Name</th><td>John Smith</td></tr>
            <tr><th>Birth</th><td>Dec 1850 Illinois, USA</td></tr>
            <tr><th>Death</th><td>1920 Kansas, USA</td></tr>
          </table>
        </div>

        NOTE: Ancestry requires subscription and structure changes frequently
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []

        # Find actual result cards (not UI elements)
        result_cards = soup.find_all('div', class_='global-results-card')

        print(f"[DEBUG] Found {len(result_cards)} result cards in Ancestry HTML")

        for card in result_cards[:20]:
            try:
                record = self._extract_person(card, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                print(f"[DEBUG] Failed to extract person: {e}")
                continue

        return records
    
    def _extract_person(self, card, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single Ancestry result card"""

        # Find the data table
        table = card.find('table', class_='tableHorizontal')
        if not table:
            return None

        # Extract URL from the title link
        title_link = card.find('a', class_='global-results-title-link')
        url = ''
        if title_link:
            url = title_link.get('href', '')
            if url and not url.startswith('http'):
                url = f"https://www.ancestry.com{url}"

        # Parse table rows
        data = {}
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td:
                key = th.get_text(strip=True).lower()
                value = td.get_text(strip=True)
                data[key] = value

        # Extract name (remove user corrections in brackets)
        name = data.get('name', '')
        name = re.sub(r'\[.*?\]', '', name).strip()
        name = re.sub(r'\s+', ' ', name)  # Normalize whitespace

        # Extract birth info
        birth_year = None
        birth_place = None
        birth_text = data.get('birth', '')
        if birth_text:
            # Format: "Dec 1850 Illinois, USA" or "1850 Illinois"
            birth_match = re.search(r'(\d{4})\s*(.+)?', birth_text)
            if birth_match:
                birth_year = int(birth_match.group(1))
                if birth_match.group(2):
                    birth_place = birth_match.group(2).strip()

        # Extract death info
        death_year = None
        death_text = data.get('death', '')
        if death_text:
            death_match = re.search(r'(\d{4})', death_text)
            if death_match:
                death_year = int(death_match.group(1))

        if not name:
            return None

        record = {
            'name': name,
            'birth_year': birth_year,
            'birth_place': birth_place,
            'death_year': death_year,
            'url': url,
            'source': self.source_name,
            'raw_data': data
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

