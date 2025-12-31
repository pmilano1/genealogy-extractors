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
        <div class="record_card">
          <a class="record_name" href="/...">Name</a>
          <ul class="results_field_list">
            <li class="fields_list_item birth">
              <span class="label">Birth</span>
              <span class="value">1874 - Location</span>
            </li>
          </ul>
        </div>

        NOTE: MyHeritage requires subscription
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []

        # Find record cards
        result_items = soup.find_all('div', class_='record_card')

        self.debug(f"Found {len(result_items)} result items in MyHeritage HTML")

        for item in result_items[:20]:
            try:
                record = self._extract_person(item, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                self.debug(f"Failed to extract person: {e}")
                continue

        return records
    
    def _extract_person(self, element, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single MyHeritage result"""

        # Extract name and URL
        link = element.find('a', class_='record_name')
        if not link:
            return None

        name = link.get_text(strip=True)
        url = link.get('href', '')
        if url and not url.startswith('http'):
            url = f"https://www.myheritage.com{url}"

        # Extract collection name
        collection_elem = element.find('div', class_='collection_name')
        collection = collection_elem.get_text(strip=True) if collection_elem else None

        # Initialize data fields
        birth_year = None
        birth_place = None
        birth_date = None
        death_year = None
        death_place = None
        death_date = None

        # Relationship data
        father = None
        mother = None
        parents = None
        spouse = None
        children = []
        siblings = []

        # Parse field list items
        field_list = element.find('ul', class_='results_field_list')
        if field_list:
            for item in field_list.find_all('li', class_='fields_list_item'):
                label_elem = item.find('span', class_='label')
                value_elem = item.find('span', class_='value')

                if not label_elem or not value_elem:
                    continue

                label = label_elem.get_text(strip=True).lower()
                value = value_elem.get_text(strip=True)

                if 'birth' in label:
                    # Parse "1874 - Location" or "Apr 3 1874 - Location"
                    year_match = re.search(r'\b(\d{4})\b', value)
                    if year_match:
                        birth_year = int(year_match.group(1))
                    # Extract full date if present
                    date_match = re.search(r'([A-Za-z]+\s+\d{1,2}\s+\d{4})', value)
                    if date_match:
                        birth_date = date_match.group(1)
                    # Extract location (after dash)
                    if ' - ' in value:
                        birth_place = value.split(' - ', 1)[1].strip()

                elif 'death' in label:
                    year_match = re.search(r'\b(\d{4})\b', value)
                    if year_match:
                        death_year = int(year_match.group(1))
                    date_match = re.search(r'([A-Za-z]+\s+\d{1,2}\s+\d{4})', value)
                    if date_match:
                        death_date = date_match.group(1)
                    if ' - ' in value:
                        death_place = value.split(' - ', 1)[1].strip()

                elif 'father' in label:
                    father = value

                elif 'mother' in label:
                    mother = value

                elif 'parents' in label:
                    parents = value

                elif 'wife' in label or 'husband' in label or 'spouse' in label:
                    spouse = value

                elif 'children' in label or 'son' in label or 'daughter' in label:
                    # Split by comma for multiple children
                    children.extend([c.strip() for c in value.split(',')])

                elif 'sibling' in label:
                    siblings.extend([s.strip() for s in value.split(',')])

        record = {
            'name': name,
            'birth_year': birth_year,
            'birth_place': birth_place,
            'death_year': death_year,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'collection': collection,
                'birth_date': birth_date,
                'death_date': death_date,
                'death_place': death_place,
                'father': father,
                'mother': mother,
                'parents': parents,
                'spouse': spouse,
                'children': children if children else None,
                'siblings': siblings if siblings else None
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

