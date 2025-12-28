"""
Find A Grave Record Extractor
Parses Find A Grave search results and extracts individual memorial records
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class FindAGraveExtractor(BaseRecordExtractor):
    """Extract records from Find A Grave search results"""
    
    def __init__(self):
        super().__init__("Find A Grave")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract memorial records from Find A Grave content

        Works with both full HTML and partial content.
        If no memorial items found, returns empty list (which signals NO_MATCH).
        """
        records = []

        # Try parsing as HTML first
        soup = BeautifulSoup(content, 'html.parser')
        memorial_items = soup.find_all('div', class_='memorial-item')

        if memorial_items:
            print(f"[DEBUG] Found {len(memorial_items)} memorial items in HTML")
            for item in memorial_items[:20]:  # Limit to top 20
                try:
                    record = self._extract_memorial_from_html(item, search_params)
                    if record:
                        records.append(record)
                except Exception as e:
                    print(f"[DEBUG] Failed to extract memorial: {e}")
                    continue
        else:
            # Fallback: look for memorial IDs in text
            print(f"[DEBUG] No memorial-item divs found, trying text extraction")
            memorial_ids = re.findall(r'/memorial/(\d+)', content)
            if memorial_ids:
                print(f"[DEBUG] Found {len(memorial_ids)} memorial IDs in text")
                # Extract basic info from text around each memorial ID
                for memorial_id in memorial_ids[:20]:
                    record = self._extract_from_text(content, memorial_id, search_params)
                    if record:
                        records.append(record)

        if not records:
            print(f"[DEBUG] No records extracted - returning empty list (NO_MATCH)")

        return records

    def _extract_memorial_from_html(self, item, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a memorial-item div"""
        # Extract memorial URL and ID
        link = item.find('a', href=re.compile(r'/memorial/\d+'))
        if not link:
            return None

        url = link.get('href')
        if not url.startswith('http'):
            url = f"https://www.findagrave.com{url}"

        # Extract memorial ID
        memorial_id_match = re.search(r'/memorial/(\d+)', url)
        memorial_id = memorial_id_match.group(1) if memorial_id_match else None

        # Extract name
        name = None
        name_elem = item.find('h3') or item.find(class_=re.compile(r'name|title'))
        if name_elem:
            name = name_elem.get_text(strip=True)
        else:
            name = link.get_text(strip=True).split('\n')[0]

        # Get all text
        item_text = item.get_text('\n', strip=True)

        # Extract dates
        birth_year = None
        death_year = None
        dates_match = re.search(r'(\d{1,2}\s+\w+\s+)?(\d{4})\s*[–-]\s*(\d{1,2}\s+\w+\s+)?(\d{4})', item_text)
        if dates_match:
            birth_year = int(dates_match.group(2))
            death_year = int(dates_match.group(4))
        else:
            year_matches = re.findall(r'\b(1\d{3}|20\d{2})\b', item_text)
            if len(year_matches) >= 2:
                birth_year = int(year_matches[0])
                death_year = int(year_matches[1])
            elif len(year_matches) == 1:
                birth_year = int(year_matches[0])

        # Extract cemetery and location
        lines = [line.strip() for line in item_text.split('\n') if line.strip()]

        cemetery = None
        location = None

        for line in lines:
            if any(word in line for word in ['Cemetery', 'Churchyard', 'Memorial', 'Gardens', 'Burial']):
                if not cemetery:
                    cemetery = line
                    break

        for line in lines:
            if ',' in line and line != cemetery and line != name:
                location = line
                break

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_place': location,
            'death_place': location,
            'cemetery': cemetery,
            'url': url,
            'memorial_id': memorial_id,
            'source': self.source_name
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _extract_record_from_lines(self, lines: List[str], start_idx: int, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a single record from consecutive lines

        Expected format (with possible noise lines):
        lines[start_idx]     = Name (e.g., "John Smith")
        lines[start_idx + ?] = Dates (e.g., "15 Aug 1871 – 25 Oct 1899" or "1871 – 1899")
        lines[start_idx + ?] = Cemetery (e.g., "Cedar Grove Cemetery")
        lines[start_idx + ?] = Location (e.g., "Dorchester, Suffolk County, Massachusetts")

        Noise lines to skip: "No grave photo", "Flowers have been left.", "Plot info: ..."
        """
        if start_idx + 6 >= len(lines):  # Need some buffer for noise lines
            return None

        name = lines[start_idx]

        # Find the dates line (next line that contains a dash and a year)
        dates_line = None
        cemetery = None
        location = None

        noise_patterns = ['No grave photo', 'Flowers have been left.', 'Plot info:']

        idx = start_idx + 1
        for offset in range(1, 7):  # Look ahead up to 6 lines
            if idx >= len(lines):
                break
            line = lines[idx]

            # Skip noise lines
            if any(pattern in line for pattern in noise_patterns):
                idx += 1
                continue

            # Look for dates line (contains dash and year)
            if dates_line is None and ('–' in line or '-' in line) and re.search(r'\d{4}', line):
                dates_line = line
                idx += 1
                continue

            # After dates, next non-noise line is cemetery
            if dates_line and cemetery is None:
                if not any(pattern in line for pattern in noise_patterns):
                    cemetery = line
                    idx += 1
                    continue

            # After cemetery, next non-noise line is location
            if cemetery and location is None:
                if not any(pattern in line for pattern in noise_patterns):
                    location = line
                    break

            idx += 1

        # Validate we got all required fields
        if not dates_line or not cemetery or not location:
            return None

        # Extract birth and death years from dates line
        # Formats: "15 Aug 1871 – 25 Oct 1899", "1871 – 1899", "1879 – 1968"
        birth_year = None
        death_year = None

        # Try to find years in the dates line
        year_matches = re.findall(r'\b(1\d{3}|20\d{2})\b', dates_line)
        if len(year_matches) >= 2:
            birth_year = int(year_matches[0])
            death_year = int(year_matches[1])
        elif len(year_matches) == 1:
            # Only one year - could be birth or death
            birth_year = int(year_matches[0])

        # Build URL (we don't have memorial ID from accessibility tree, so use search URL)
        # In a real implementation, we'd need to extract this from the actual HTML
        url = f"https://www.findagrave.com/memorial/search?firstname={search_params.get('given_name', '')}&lastname={search_params.get('surname', '')}"

        # Build record
        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_place': location,
            'death_place': location,
            'cemetery': cemetery,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'dates_line': dates_line,
                'cemetery': cemetery,
                'location': location
            }
        }

        # Calculate match score
        record['match_score'] = self.calculate_match_score(record, search_params)

        return record
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if Find A Grave page has results"""
        # Find A Grave specific indicators
        indicators = [
            r'\d+\s+memorials?',
            r'\d+\s+results?',
            'memorial/',
            'search results'
        ]
        
        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False


# Example usage:
if __name__ == "__main__":
    # Test with sample HTML
    sample_html = """
    <div class="memorial-item">
        <a href="/memorial/12345">John Smith</a>
        <div class="dates">b. 1875 - d. 1950</div>
        <div class="location">London, England</div>
    </div>
    """
    
    extractor = FindAGraveExtractor()
    search_params = {
        'surname': 'Smith',
        'given_name': 'John',
        'location': 'London',
        'year_min': 1870,
        'year_max': 1880
    }
    
    records = extractor.extract_records(sample_html, search_params)
    print(f"Extracted {len(records)} records")
    for record in records:
        print(f"  - {record['name']} (b. {record['birth_year']}) - Score: {record['match_score']}")

