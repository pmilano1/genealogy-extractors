"""
BillionGraves Record Extractor
Parses BillionGraves search results and extracts cemetery/grave records
Similar to Find A Grave but different HTML structure
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class BillionGravesExtractor(BaseRecordExtractor):
    """Extract records from BillionGraves search results"""

    def __init__(self):
        super().__init__("BillionGraves")

    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract grave records from BillionGraves content"""
        records = []

        # Check for no results
        if self._is_no_results(content):
            print(f"[DEBUG] BillionGraves: No results page detected")
            return []

        # Check for error page
        if self._is_error_page(content):
            print(f"[DEBUG] BillionGraves: Error page detected")
            return []

        soup = BeautifulSoup(content, 'html.parser')

        # BillionGraves uses divs with class containing 'record' or 'result'
        # Look for result cards/rows
        result_items = (
            soup.find_all('div', class_=re.compile(r'result|record|grave-card')) or
            soup.find_all('a', class_=re.compile(r'result|record|grave')) or
            soup.find_all('tr', class_=re.compile(r'result|record'))
        )

        if result_items:
            print(f"[DEBUG] BillionGraves: Found {len(result_items)} result items")
            for item in result_items[:20]:
                try:
                    record = self._extract_record(item, search_params)
                    if record:
                        records.append(record)
                except Exception as e:
                    print(f"[DEBUG] BillionGraves extraction error: {e}")
                    continue
        else:
            # Fallback: look for grave links
            grave_links = soup.find_all('a', href=re.compile(r'/grave/\d+'))
            if grave_links:
                print(f"[DEBUG] BillionGraves: Found {len(grave_links)} grave links")
                for link in grave_links[:20]:
                    record = self._extract_from_link(link, search_params)
                    if record:
                        records.append(record)

        return records

    def _extract_record(self, item, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a result item"""
        # Get text content
        text = item.get_text(' ', strip=True)

        # Find link to grave page
        link = item.find('a', href=re.compile(r'/grave/\d+'))
        if not link:
            link = item if item.name == 'a' and item.get('href') else None

        url = None
        grave_id = None
        if link:
            href = link.get('href', '')
            if not href.startswith('http'):
                url = f"https://billiongraves.com{href}"
            else:
                url = href
            grave_match = re.search(r'/grave/(\d+)', href)
            grave_id = grave_match.group(1) if grave_match else None

        # Extract name (usually in h2, h3, or strong)
        name_elem = item.find(['h2', 'h3', 'h4', 'strong', 'b'])
        name = name_elem.get_text(strip=True) if name_elem else None
        if not name and link:
            name = link.get_text(strip=True)

        # Extract years
        year_matches = re.findall(r'\b(1[5-9]\d{2}|20[0-2]\d)\b', text)
        birth_year = int(year_matches[0]) if year_matches else None
        death_year = int(year_matches[1]) if len(year_matches) > 1 else None

        # Extract location/cemetery
        location = None
        cemetery = None
        for span in item.find_all(['span', 'div', 'p']):
            span_text = span.get_text(strip=True)
            if any(word in span_text for word in ['Cemetery', 'Memorial', 'Graveyard']):
                cemetery = span_text
            elif ',' in span_text and len(span_text) < 100:
                location = span_text

        if not name:
            return None

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_place': location,
            'death_place': location,
            'cemetery': cemetery,
            'url': url,
            'grave_id': grave_id,
            'source': self.source_name
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _extract_from_link(self, link, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic info from a grave link"""
        href = link.get('href', '')
        name = link.get_text(strip=True)
        url = f"https://billiongraves.com{href}" if not href.startswith('http') else href

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
        no_result_patterns = [
            r'no results found',
            r'no records found',
            r'no graves found',
            r'0 results',
            r'did not find any',
            r'no matches'
        ]
        content_lower = content.lower()
        return any(re.search(p, content_lower) for p in no_result_patterns)

    def _is_error_page(self, content: str) -> bool:
        """Check for error page indicators"""
        error_patterns = [
            r'error 404',
            r'page not found',
            r'something went wrong',
            r'server error'
        ]
        content_lower = content.lower()
        return any(re.search(p, content_lower) for p in error_patterns)

