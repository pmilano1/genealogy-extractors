"""
Digitalarkivet (Norwegian Digital Archives) Record Extractor
Free Norwegian archives - church records, census, emigration
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class DigitalarkivetExtractor(BaseRecordExtractor):
    """Extract records from Digitalarkivet (Norwegian Archives) search results"""

    def __init__(self):
        super().__init__("Digitalarkivet")

    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from Digitalarkivet search results"""
        records = []

        # Check for no results
        if self._is_no_results(content):
            self.debug(f"Digitalarkivet: No results page detected")
            return []

        # Check for error page
        if self._is_error_page(content):
            self.debug(f"Digitalarkivet: Error page detected")
            return []

        soup = BeautifulSoup(content, 'html.parser')

        # Look for result rows in table or list format
        result_rows = (
            soup.find_all('tr', class_=re.compile(r'result|record|hit')) or
            soup.find_all('div', class_=re.compile(r'result|record|hit|person')) or
            soup.find_all('li', class_=re.compile(r'result|record|hit'))
        )

        if result_rows:
            self.debug(f"Digitalarkivet: Found {len(result_rows)} result rows")
            for row in result_rows[:20]:
                try:
                    record = self._extract_record(row, search_params)
                    if record:
                        records.append(record)
                except Exception as e:
                    self.debug(f"Digitalarkivet extraction error: {e}")
                    continue
        else:
            # Fallback: look for links to person/source pages
            person_links = soup.find_all('a', href=re.compile(r'/(person|kilde|source)/'))
            if person_links:
                self.debug(f"Digitalarkivet: Found {len(person_links)} person links")
                for link in person_links[:20]:
                    record = self._extract_from_link(link, search_params)
                    if record:
                        records.append(record)

        return records

    def _extract_record(self, row, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a result row"""
        text = row.get_text(' ', strip=True)

        # Find link to person/source page
        link = row.find('a', href=re.compile(r'/(person|kilde|source)/'))
        url = None
        if link:
            href = link.get('href', '')
            if not href.startswith('http'):
                url = f"https://www.digitalarkivet.no{href}"
            else:
                url = href

        # Extract name from cells or prominent elements
        name = None
        name_elem = row.find(['th', 'td', 'strong', 'b'])
        if name_elem:
            name = name_elem.get_text(strip=True)
        elif link:
            name = link.get_text(strip=True)

        # Extract years
        year_matches = re.findall(r'\b(1[5-9]\d{2}|20[0-2]\d)\b', text)
        birth_year = int(year_matches[0]) if year_matches else None
        death_year = int(year_matches[1]) if len(year_matches) > 1 else None

        # Extract location (Norwegian places)
        location = None
        location_patterns = [
            r'([\wæøåÆØÅ]+(?:,\s*[\wæøåÆØÅ]+)*)',  # Norwegian chars
        ]
        # Look for td/span with location info
        for cell in row.find_all(['td', 'span']):
            cell_text = cell.get_text(strip=True)
            # Norwegian locations often have kommune, fylke
            if any(word in cell_text.lower() for word in ['kommune', 'fylke', 'sogn', 'prestegjeld']):
                location = cell_text
                break

        # Record type (kirkebøker=church, folketelling=census, emigrant=emigration)
        record_type = None
        if 'kirkeb' in text.lower() or 'dåp' in text.lower():
            record_type = 'church'
        elif 'folketelling' in text.lower() or 'census' in text.lower():
            record_type = 'census'
        elif 'emigrant' in text.lower() or 'utvandring' in text.lower():
            record_type = 'emigration'

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
        """Extract basic info from a person link"""
        href = link.get('href', '')
        name = link.get_text(strip=True)
        url = f"https://www.digitalarkivet.no{href}" if not href.startswith('http') else href

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
            r'ingen treff',  # Norwegian for "no hits"
            r'no results',
            r'0 treff',
            r'fant ingen',  # "found none"
            r'no records found'
        ]
        content_lower = content.lower()
        return any(re.search(p, content_lower) for p in patterns)

    def _is_error_page(self, content: str) -> bool:
        """Check for error page indicators"""
        patterns = [
            r'error 404',
            r'page not found',
            r'siden finnes ikke',  # "page does not exist"
            r'server error'
        ]
        content_lower = content.lower()
        return any(re.search(p, content_lower) for p in patterns)

