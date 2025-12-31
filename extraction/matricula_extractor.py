"""
Matricula Online Record Extractor
Free Catholic church records from Germany, Austria, Poland, and other regions
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class MatriculaExtractor(BaseRecordExtractor):
    """Extract records from Matricula Online search results"""

    def __init__(self):
        super().__init__("Matricula")

    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from Matricula search results"""
        records = []

        # Check for no results
        if self._is_no_results(content):
            self.debug(f"Matricula: No results page detected")
            return []

        # Check for error page
        if self._is_error_page(content):
            self.debug(f"Matricula: Error page detected")
            return []

        soup = BeautifulSoup(content, 'html.parser')

        # Matricula typically shows results in table or list format
        result_items = (
            soup.find_all('tr', class_=re.compile(r'result|record|entry')) or
            soup.find_all('div', class_=re.compile(r'result|record|entry|hit')) or
            soup.find_all('li', class_=re.compile(r'result|record'))
        )

        if result_items:
            self.debug(f"Matricula: Found {len(result_items)} result items")
            for item in result_items[:20]:
                try:
                    record = self._extract_record(item, search_params)
                    if record:
                        records.append(record)
                except Exception as e:
                    self.debug(f"Matricula extraction error: {e}")
                    continue
        else:
            # Fallback: look for links to register pages
            register_links = soup.find_all('a', href=re.compile(r'/(register|matriken|book)/'))
            if register_links:
                self.debug(f"Matricula: Found {len(register_links)} register links")
                for link in register_links[:20]:
                    record = self._extract_from_link(link, search_params)
                    if record:
                        records.append(record)

        return records

    def _extract_record(self, item, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a result item"""
        text = item.get_text(' ', strip=True)

        # Find link to register/record
        link = item.find('a')
        url = None
        if link:
            href = link.get('href', '')
            if not href.startswith('http'):
                url = f"https://data.matricula-online.eu{href}"
            else:
                url = href

        # Extract name
        name = None
        name_elem = item.find(['strong', 'b', 'span'])
        if name_elem:
            name = name_elem.get_text(strip=True)
        elif link:
            name = link.get_text(strip=True)

        # Extract years
        year_matches = re.findall(r'\b(1[5-9]\d{2}|20[0-2]\d)\b', text)
        birth_year = int(year_matches[0]) if year_matches else None
        death_year = int(year_matches[1]) if len(year_matches) > 1 else None

        # Extract location (German/Austrian places)
        location = None
        # Look for parish/diocese info
        for pattern in [r'Pfarr\w*', r'Diöze\w*', r'Gemeinde', r'Parish']:
            match = re.search(rf'{pattern}[:\s]+([^,\n]+)', text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                break

        # Record type (Taufen=baptisms, Trauungen=marriages, Sterbefälle=deaths)
        record_type = None
        text_lower = text.lower()
        if 'tauf' in text_lower or 'baptism' in text_lower:
            record_type = 'baptism'
        elif 'trau' in text_lower or 'marriage' in text_lower or 'heirat' in text_lower:
            record_type = 'marriage'
        elif 'sterb' in text_lower or 'death' in text_lower or 'tod' in text_lower:
            record_type = 'death'

        if not name or len(name) < 2:
            return None

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_place': location,
            'url': url,
            'record_type': record_type,
            'source': self.source_name
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _extract_from_link(self, link, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic info from a register link"""
        href = link.get('href', '')
        name = link.get_text(strip=True)
        url = f"https://data.matricula-online.eu{href}" if not href.startswith('http') else href

        if not name or len(name) < 2:
            return None

        record = {
            'name': name,
            'url': url,
            'source': self.source_name
        }
        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _is_no_results(self, content: str) -> bool:
        """Check for no results indicators"""
        patterns = [
            r'keine ergebnisse',  # German
            r'no results',
            r'0 treffer',
            r'nichts gefunden',
            r'no records found'
        ]
        content_lower = content.lower()
        return any(re.search(p, content_lower) for p in patterns)

    def _is_error_page(self, content: str) -> bool:
        """Check for error page indicators"""
        patterns = [r'error 404', r'page not found', r'seite nicht gefunden', r'server error']
        content_lower = content.lower()
        return any(re.search(p, content_lower) for p in patterns)

