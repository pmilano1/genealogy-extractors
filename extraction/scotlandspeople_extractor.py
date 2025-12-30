"""
ScotlandsPeople Record Extractor
Scottish civil registration, census, and church records
Note: Full records require payment, but index is searchable
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class ScotlandsPeopleExtractor(BaseRecordExtractor):
    """Extract records from ScotlandsPeople search results"""

    def __init__(self):
        super().__init__("ScotlandsPeople")

    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from ScotlandsPeople search results"""
        records = []

        # Check for no results
        if self._is_no_results(content):
            print(f"[DEBUG] ScotlandsPeople: No results page detected")
            return []

        # Check for error page
        if self._is_error_page(content):
            print(f"[DEBUG] ScotlandsPeople: Error page detected")
            return []

        soup = BeautifulSoup(content, 'html.parser')

        # ScotlandsPeople uses tables for results
        result_tables = soup.find_all('table', class_=re.compile(r'result|record|search'))
        if result_tables:
            for table in result_tables:
                rows = table.find_all('tr')[1:]  # Skip header
                print(f"[DEBUG] ScotlandsPeople: Found {len(rows)} result rows")
                for row in rows[:20]:
                    try:
                        record = self._extract_from_table_row(row, search_params)
                        if record:
                            records.append(record)
                    except Exception as e:
                        print(f"[DEBUG] ScotlandsPeople extraction error: {e}")
                        continue
        else:
            # Fallback: look for result divs
            result_items = soup.find_all(['div', 'li'], class_=re.compile(r'result|record'))
            if result_items:
                print(f"[DEBUG] ScotlandsPeople: Found {len(result_items)} result items")
                for item in result_items[:20]:
                    record = self._extract_from_div(item, search_params)
                    if record:
                        records.append(record)

        return records

    def _extract_from_table_row(self, row, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a table row"""
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            return None

        cell_texts = [cell.get_text(strip=True) for cell in cells]
        full_text = ' '.join(cell_texts)

        # Find link to record
        link = row.find('a')
        url = None
        if link:
            href = link.get('href', '')
            if not href.startswith('http'):
                url = f"https://www.scotlandspeople.gov.uk{href}"
            else:
                url = href

        # Extract name (usually first cell or in link)
        name = None
        if link:
            name = link.get_text(strip=True)
        if not name and cell_texts:
            name = cell_texts[0]

        # Extract years
        year_matches = re.findall(r'\b(1[7-9]\d{2}|19\d{2}|20[0-2]\d)\b', full_text)
        birth_year = None
        death_year = None

        for i, text in enumerate(cell_texts):
            if re.match(r'^1[89]\d{2}$', text) or re.match(r'^19\d{2}$', text):
                if birth_year is None:
                    birth_year = int(text)
                else:
                    death_year = int(text)

        if not birth_year and year_matches:
            birth_year = int(year_matches[0])
            if len(year_matches) > 1:
                death_year = int(year_matches[1])

        # Extract location (Scottish places)
        location = None
        for text in cell_texts[1:]:
            # Scottish locations: Edinburgh, Glasgow, Aberdeen, etc.
            if any(word in text for word in ['Edinburgh', 'Glasgow', 'Aberdeen', 'Dundee', 'Parish']):
                location = text
                break

        # Record type
        record_type = None
        if 'birth' in full_text.lower() or 'baptism' in full_text.lower():
            record_type = 'birth'
        elif 'death' in full_text.lower() or 'burial' in full_text.lower():
            record_type = 'death'
        elif 'marriage' in full_text.lower():
            record_type = 'marriage'
        elif 'census' in full_text.lower():
            record_type = 'census'

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

    def _extract_from_div(self, item, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a div/list item"""
        text = item.get_text(' ', strip=True)
        link = item.find('a')
        url = None
        if link:
            href = link.get('href', '')
            url = f"https://www.scotlandspeople.gov.uk{href}" if not href.startswith('http') else href

        name = link.get_text(strip=True) if link else None
        year_matches = re.findall(r'\b(1[7-9]\d{2}|19\d{2})\b', text)
        birth_year = int(year_matches[0]) if year_matches else None

        if not name:
            return None

        record = {
            'name': name,
            'birth_year': birth_year,
            'url': url,
            'source': self.source_name
        }
        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _is_no_results(self, content: str) -> bool:
        """Check for no results indicators"""
        patterns = [
            r'no results found',
            r'no records found',
            r'0 results',
            r'no matching records',
            r'your search returned no results'
        ]
        content_lower = content.lower()
        return any(re.search(p, content_lower) for p in patterns)

    def _is_error_page(self, content: str) -> bool:
        """Check for error page indicators"""
        patterns = [r'error 404', r'page not found', r'server error', r'service unavailable']
        content_lower = content.lower()
        return any(re.search(p, content_lower) for p in patterns)

