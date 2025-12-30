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
        """Extract data from a single Ancestry result card

        Ancestry table fields may include:
        - Name, Birth, Death, Marriage, Residence
        - Mother, Father (for baptism records)
        - Baptism (date and place)
        """

        # Find the data table
        table = card.find('table', class_='tableHorizontal')
        if not table:
            return None

        # Extract URL from the title link
        title_link = card.find('a', class_='global-results-title-link')
        url = ''
        collection_name = ''
        if title_link:
            url = title_link.get('href', '')
            if url and not url.startswith('http'):
                url = f"https://www.ancestry.com{url}"
            # Get collection name from link text
            collection_name = title_link.get_text(strip=True)

        # Parse table rows
        data = {}
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td:
                key = th.get_text(strip=True).lower()
                # Use separator to preserve spaces between elements
                value = td.get_text(' ', strip=True)
                data[key] = value

        # Extract name - clean up properly
        name = data.get('name', '')

        # Remove user corrections in brackets first
        name = re.sub(r'\[.*?\]', '', name).strip()

        # Remove angle brackets (alternate surnames)
        name = re.sub(r'<.*?>', '', name).strip()

        # Clean up special characters and normalize whitespace
        name = name.replace('??', '').strip()
        name = re.sub(r'\s+', ' ', name)

        # Extract birth info
        birth_year = None
        birth_place = None
        birth_date = None
        birth_text = data.get('birth', '')
        if birth_text:
            # Format: "27 Dec 1850 Illinois, USA" or "Dec 1850 Illinois" or "1850 Illinois"
            # Try full date first
            full_date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', birth_text)
            if full_date_match:
                birth_date = full_date_match.group(1)

            year_match = re.search(r'(\d{4})', birth_text)
            if year_match:
                birth_year = int(year_match.group(1))
                # Extract location after the year
                after_year = birth_text[birth_text.find(str(birth_year)) + 4:].strip()
                if after_year:
                    birth_place = after_year

        # Extract death info
        death_year = None
        death_place = None
        death_text = data.get('death', '')
        if death_text:
            death_match = re.search(r'(\d{4})', death_text)
            if death_match:
                death_year = int(death_match.group(1))
                after_year = death_text[death_text.find(str(death_year)) + 4:].strip()
                if after_year:
                    death_place = after_year

        # Extract marriage info
        marriage_year = None
        marriage_text = data.get('marriage', '')
        if marriage_text:
            marriage_match = re.search(r'(\d{4})', marriage_text)
            if marriage_match:
                marriage_year = int(marriage_match.group(1))

        # Extract parents
        father = data.get('father', '').strip() or None
        mother = data.get('mother', '').strip() or None

        # Extract baptism info (may have date/place if no birth)
        baptism_text = data.get('baptism', '')
        if baptism_text and not birth_year:
            # Try to extract year from baptism if no birth year
            baptism_match = re.search(r'(\d{4})', baptism_text)
            if baptism_match:
                birth_year = int(baptism_match.group(1))
            if not birth_place:
                # Extract location from baptism
                place_match = re.search(r'\d{4}\s+(.+)', baptism_text)
                if place_match:
                    birth_place = place_match.group(1).strip()

        if not name:
            return None

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_date': birth_date,
            'birth_place': birth_place,
            'death_place': death_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'father': father,
                'mother': mother,
                'marriage_year': marriage_year,
                'collection': collection_name,
                'baptism': baptism_text if baptism_text else None,
                'residence': data.get('residence'),
                'all_fields': data
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

