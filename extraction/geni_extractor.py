"""
Geni.com Record Extractor
Uses CDP browser scraping for Geni search results

URL Pattern: https://www.geni.com/search?search_type=people&names={names}
Requires logged-in session via CDP browser
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class GeniExtractor(BaseRecordExtractor):
    """Extract records from Geni.com search results (HTML)"""

    def __init__(self):
        super().__init__("Geni")

    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from Geni HTML search results

        Geni search results structure (table-based):
        - Each result is a <tr class="profile-layout-grid"> with data-profile-id
        - Name cell contains <a href="/people/{slug}/{id}">Name</a>
        - Location in <div class="small"> before dates
        - Dates in <div class="small quiet"> format "(YYYY - YYYY)"
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []

        # Find all profile rows in the results table
        profile_rows = soup.find_all('tr', class_='profile-layout-grid')

        print(f"[DEBUG] Geni: Found {len(profile_rows)} profile rows")

        for row in profile_rows[:20]:  # Limit to 20 results
            try:
                record = self._extract_profile_from_row(row, search_params)
                if record and record.get('name'):
                    records.append(record)
            except Exception as e:
                print(f"[DEBUG] Geni extraction error: {e}")
                continue

        print(f"[DEBUG] Geni: Extracted {len(records)} records")
        return records

    def _extract_profile_from_row(self, row, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a Geni profile table row

        Row structure:
        <tr class="profile-layout-grid" data-profile-id="..." data-deceased="true" data-privacy="master">
          <td class="name-grid-area">
            <a href="/people/Name/ID">Name</a>
            <div class="small">"Nickname"</div>
            <div class="small">Location</div>
            <div class="small quiet">(birth - death)</div>
          </td>
          <td class="immediate-family-grid-area">
            Son of Father and Mother
            Husband of Spouse
            Father of Child1; Child2
          </td>
        </tr>
        """
        # Get profile ID and metadata from data attributes
        profile_id = row.get('data-profile-id', '')
        is_deceased = row.get('data-deceased', '') == 'true'
        privacy = row.get('data-privacy', '')  # 'master', 'public', etc.

        # Find the name cell
        name_cell = row.find('td', class_='name-grid-area')
        if not name_cell:
            return None

        # Get name from the main profile link (not action links)
        name_link = name_cell.find('a', href=re.compile(r'^/people/[^/]+/\d+$'))
        if not name_link:
            return None

        name = name_link.get_text(strip=True)
        if not name:
            return None

        # Build URL
        url = name_link.get('href', '')
        if url and not url.startswith('http'):
            url = f"https://www.geni.com{url}"

        # Extract nickname and location from the small divs
        birth_place = None
        nickname = None
        small_divs = name_cell.find_all('div', class_='small')
        for div in small_divs:
            # Skip the dates div (has 'quiet' class)
            if 'quiet' in div.get('class', []):
                continue
            # Skip area-title divs
            if 'area-title' in div.get('class', []):
                continue
            # Skip similar_profiles divs
            if 'similar_profiles' in div.get('class', []):
                continue
            text = div.get_text(strip=True)
            if not text:
                continue
            # Check if it's a nickname (in quotes)
            if text.startswith('"') and text.endswith('"'):
                nickname = text.strip('"')
            elif not birth_place:
                # First non-nickname text is location
                birth_place = text

        # Extract birth/death years from the quiet div
        birth_year = None
        death_year = None
        date_div = name_cell.find('div', class_='quiet')
        if date_div:
            date_text = date_div.get_text(strip=True)
            # Format: "(1821 - 1871)" or "(c.1595 - bef.1663)" or "Birth: estimated between..."
            years = re.findall(r'(\d{4})', date_text)
            if len(years) >= 1:
                birth_year = int(years[0])
            if len(years) >= 2:
                death_year = int(years[1])

        # Extract family information from immediate-family-grid-area
        father = None
        mother = None
        spouse = None
        children = []
        siblings = []

        family_cell = row.find('td', class_='immediate-family-grid-area')
        if family_cell:
            family_text = family_cell.get_text(separator='\n', strip=True)
            for line in family_text.split('\n'):
                line = line.strip()
                if not line or line == 'Family:':
                    continue

                # Parse "Son/Daughter of Father and Mother"
                parent_match = re.match(r'(?:Son|Daughter|Child)\s+of\s+(.+?)\s+and\s+(.+)', line, re.IGNORECASE)
                if parent_match:
                    father = parent_match.group(1).strip()
                    mother = parent_match.group(2).strip()
                    continue

                # Parse "Husband/Wife of Spouse"
                spouse_match = re.match(r'(?:Husband|Wife|Spouse)\s+of\s+(.+)', line, re.IGNORECASE)
                if spouse_match:
                    spouse = spouse_match.group(1).strip()
                    continue

                # Parse "Father/Mother of Child1; Child2; ..."
                children_match = re.match(r'(?:Father|Mother|Parent)\s+of\s+(.+)', line, re.IGNORECASE)
                if children_match:
                    children_text = children_match.group(1)
                    # Split by semicolon or "and"
                    for child in re.split(r';\s*|\s+and\s+', children_text):
                        child = child.strip()
                        if child and child not in children:
                            children.append(child)
                    continue

                # Parse "Brother/Sister of Sibling1; Sibling2; ..."
                siblings_match = re.match(r'(?:Brother|Sister|Sibling|Half brother|Half sister)\s+of\s+(.+)', line, re.IGNORECASE)
                if siblings_match:
                    siblings_text = siblings_match.group(1)
                    for sibling in re.split(r';\s*|\s+and\s+', siblings_text):
                        sibling = sibling.strip()
                        if sibling and sibling not in siblings:
                            siblings.append(sibling)
                    continue

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_place': birth_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'profile_id': profile_id,
                'nickname': nickname,
                'is_deceased': is_deceased,
                'privacy': privacy,
                'father': father,
                'mother': mother,
                'spouse': spouse,
                'children': children if children else None,
                'siblings': siblings if siblings else None
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _has_results_indicator(self, content: str) -> bool:
        """Check if Geni page has results"""
        indicators = [
            r'Showing \d+-\d+ of [\d,]+ people',
            r'\d+-\d+ of \d+ people',
            r'/people/',
            'Search Results'
        ]

        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

