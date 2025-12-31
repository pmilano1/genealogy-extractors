"""
Filae Record Extractor
Parses Filae.com French genealogy records
"""

import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base import BaseRecordExtractor


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
        
        self.debug(f"Found {len(result_items)} result items in Filae HTML")
        
        for item in result_items[:20]:
            try:
                record = self._extract_person(item, search_params)
                if record and record.get('name'):
                    records.append(record)
            except Exception as e:
                self.debug(f"Filae extraction error: {e}")
                continue
        
        return records
    
    def _extract_person(self, item, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single Filae result

        Filae 2024 structure (data-testid="PersonCard"):
        - Name in p.names
        - Life span in p.css-f08yb with birth-death years
        - Parents in PersonFamily > li with "Parents"
        - Spouse in PersonFamily > li with "Conjoint"
        - Events in PersonEvents with event type, date, location
        - Source in PersonSource
        - Image preview in img.css-zipvlc
        """
        # Look for PersonCard or use generic extraction
        person_card = item.find('a', {'data-testid': 'PersonCard'}) or item.find('a', class_=re.compile(r'PersonCard|ibktxe'))

        # Try to find name from various locations
        name = None
        name_elem = item.find('p', class_=re.compile(r'names|b2ax9x'))
        if name_elem:
            name = name_elem.get_text(strip=True)
        if not name:
            name_elem = item.find(class_=re.compile(r'name|nom|person', re.I)) or item.find('strong')
            if name_elem:
                name = name_elem.get_text(strip=True)

        if not name:
            return None

        # Extract life span (birth - death)
        birth_year = None
        death_year = None
        lifespan_elem = item.find('p', class_=re.compile(r'f08yb'))
        if lifespan_elem:
            lifespan_text = lifespan_elem.get_text(strip=True)
            years = re.findall(r'\b(1[5-9]\d{2}|20[0-2]\d)\b', lifespan_text)
            if len(years) >= 1:
                birth_year = int(years[0])
            if len(years) >= 2:
                death_year = int(years[1])
        else:
            # Fallback to generic year search
            text = item.get_text()
            year_match = re.search(r'\b(1[7-9]\d{2}|20[0-2]\d)\b', text)
            if year_match:
                birth_year = int(year_match.group(1))

        # Extract parents
        father = None
        mother = None
        spouse = None
        spouse_birth = None
        spouse_death = None

        family_section = item.find('ul', {'data-testid': 'PersonFamily'}) or item.find('ul', class_=re.compile(r'va5bsd'))
        if family_section:
            for li in family_section.find_all('li', class_=re.compile(r'wiwzbp')):
                label = li.find('p', class_=re.compile(r'11r40s0'))
                if label:
                    label_text = label.get_text(strip=True).lower()
                    names = li.find_all('p', class_=re.compile(r'break-word'))
                    if 'parent' in label_text:
                        for i, name_p in enumerate(names):
                            # Extract surname and given name separately for proper spacing
                            surname_span = name_p.find('span', class_=re.compile(r'wwiaj0'))
                            given_span = name_p.find('span', class_=re.compile(r'16xvjce'))
                            if surname_span and given_span:
                                person_name = f"{surname_span.get_text(strip=True)} {given_span.get_text(strip=True)}"
                            else:
                                person_name = name_p.get_text(strip=True).replace('•', '').strip()
                            if i == 0:
                                father = person_name
                            elif i == 1:
                                mother = person_name
                    elif 'conjoint' in label_text or 'spouse' in label_text:
                        spouse_elem = names[0] if names else None
                        if spouse_elem:
                            # Extract surname and given name separately for proper spacing
                            surname_span = spouse_elem.find('span', class_=re.compile(r'wwiaj0'))
                            given_span = spouse_elem.find('span', class_=re.compile(r'16xvjce'))
                            if surname_span and given_span:
                                spouse = f"{surname_span.get_text(strip=True)} {given_span.get_text(strip=True)}"
                            else:
                                spouse = spouse_elem.get_text(strip=True).replace('•', '').strip()
                            # Extract spouse years if present in the full text
                            spouse_text = spouse_elem.get_text(strip=True)
                            spouse_years = re.findall(r'\b(1[5-9]\d{2}|20[0-2]\d)\b', spouse_text)
                            if len(spouse_years) >= 1:
                                spouse_birth = int(spouse_years[0])
                            if len(spouse_years) >= 2:
                                spouse_death = int(spouse_years[1])

        # Extract events (birth, marriage, death with locations)
        events = []
        birth_place = None
        death_place = None
        marriage_year = None
        marriage_place = None

        events_section = item.find('div', {'data-testid': 'PersonEvents'}) or item.find('div', class_=re.compile(r'4zg7ak'))
        if events_section:
            for event_div in events_section.find_all('div', class_=re.compile(r'rbyf9|wivkel')):
                event_type = None
                event_year = None
                event_place = None

                # Get event type
                type_p = event_div.find('p', class_=re.compile(r'epfnk9|ellipsis'))
                if type_p:
                    event_type = type_p.get_text(strip=True).lower()

                # Get event year
                year_p = event_div.find('p', class_=re.compile(r'5z7ly2'))
                if year_p:
                    year_match = re.search(r'\b(1[5-9]\d{2}|20[0-2]\d)\b', year_p.get_text())
                    if year_match:
                        event_year = int(year_match.group(1))

                # Get event location (usually last p without special class)
                all_ps = event_div.find_all('p')
                for p in all_ps:
                    if not p.get('class') or 'wwiaj0' in str(p.get('class', [])):
                        text = p.get_text(strip=True)
                        if text and not re.match(r'^\d{4}$', text) and 'mariage' not in text.lower() and 'naissance' not in text.lower():
                            event_place = text

                if event_type:
                    events.append({'type': event_type, 'year': event_year, 'place': event_place})
                    if 'mariage' in event_type or 'marriage' in event_type:
                        marriage_year = event_year
                        marriage_place = event_place
                    elif 'naissance' in event_type or 'birth' in event_type:
                        if not birth_place:
                            birth_place = event_place
                    elif 'décès' in event_type or 'death' in event_type:
                        if not death_place:
                            death_place = event_place

        # Extract source
        source_info = None
        source_elem = item.find('p', {'data-testid': 'PersonSource'}) or item.find('p', class_=re.compile(r'va9s08'))
        if source_elem:
            source_info = source_elem.get_text(strip=True)

        # Extract image URL
        image_url = None
        img_elem = item.find('img', class_=re.compile(r'zipvlc'))
        if img_elem:
            image_url = img_elem.get('src')

        # Try to find URL
        url = None
        link = item.find('a', href=True)
        if link:
            href = link.get('href', '')
            if href and not href.startswith('http'):
                url = f"https://www.filae.com{href}"
            else:
                url = href

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_place': birth_place,
            'death_place': death_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'source_collection': source_info,
                'father': father,
                'mother': mother,
                'spouse': spouse,
                'spouse_birth_year': spouse_birth,
                'spouse_death_year': spouse_death,
                'marriage_year': marriage_year,
                'marriage_place': marriage_place,
                'events': events if events else None,
                'image_url': image_url
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

