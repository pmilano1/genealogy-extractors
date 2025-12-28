"""
FamilySearch Record Extractor
Parses FamilySearch search results (requires login)
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class FamilySearchExtractor(BaseRecordExtractor):
    """Extract records from FamilySearch search results"""
    
    def __init__(self):
        super().__init__("FamilySearch")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from FamilySearch results

        FamilySearch structure:
        <tr data-testid="/ark:/61903/1:1:NQCV-GQ3">
          <td>
            <h2>
              <a class="linkCss_l1o3aooc" href="/ark:/...">Margaret Anderson</a>
              <div>Principal<br/>Michigan, Births, 1867-1902</div>
            </h2>
          </td>
          <td>
            <div><strong>Birth</strong> <span>1869</span><br/><span>Berlin, Michigan</span></div>
          </td>
          <td>
            <div><strong>Parents</strong> Janet Anderson, William Anderson</div>
          </td>
        </tr>
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []

        # Find all result rows with ark IDs
        person_rows = soup.find_all('tr', attrs={'data-testid': re.compile(r'/ark:/')})

        print(f"[DEBUG] Found {len(person_rows)} person rows in FamilySearch HTML")

        for row in person_rows[:20]:
            try:
                record = self._extract_person(row, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                print(f"[DEBUG] Failed to extract person: {e}")
                continue

        return records
    
    def _extract_person(self, row, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single FamilySearch result row"""

        # Extract name and URL from <a class="linkCss_l1o3aooc">
        link = row.find('a', class_='linkCss_l1o3aooc')
        if not link:
            return None

        name = link.get_text(strip=True)
        url = link.get('href', '')
        if url and not url.startswith('http'):
            url = f"https://www.familysearch.org{url}"

        # Extract birth year and place from <td> with <strong>Birth</strong>
        birth_year = None
        birth_place = None

        # Find all <td> cells
        cells = row.find_all('td')
        for cell in cells:
            cell_text = cell.get_text()

            # Look for Birth section
            if 'Birth' in cell_text:
                # Extract year from <span>YYYY</span>
                year_spans = cell.find_all('span')
                for span in year_spans:
                    year_match = re.search(r'\b(1[7-9]\d{2}|20\d{2})\b', span.get_text())
                    if year_match:
                        birth_year = int(year_match.group(1))
                        break

                # Extract location (text after year)
                lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
                for line in lines:
                    if line and line != 'Birth' and not re.match(r'^\d{4}$', line):
                        birth_place = line
                        break

        # Extract parents from <td> with <strong>Parents</strong>
        parents = None
        for cell in cells:
            if 'Parents' in cell.get_text():
                parents_text = cell.get_text().replace('Parents', '').strip()
                if parents_text:
                    parents = parents_text

        record = {
            'name': name,
            'birth_year': birth_year,
            'birth_place': birth_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'parents': parents
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if FamilySearch page has results"""
        indicators = [
            r'\d+\s+results?',
            '/ark:/',
            'search results'
        ]
        
        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False

