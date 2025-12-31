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
            self.debug(f"Found {len(memorial_items)} memorial items in HTML")
            for item in memorial_items[:20]:  # Limit to top 20
                try:
                    record = self._extract_memorial_from_html(item, search_params)
                    if record:
                        records.append(record)
                except Exception as e:
                    self.debug(f"Failed to extract memorial: {e}")
                    continue
        else:
            # Fallback: look for memorial IDs in text
            self.debug(f"No memorial-item divs found, trying text extraction")
            memorial_ids = re.findall(r'/memorial/(\d+)', content)
            if memorial_ids:
                self.debug(f"Found {len(memorial_ids)} memorial IDs in text")
                # Extract basic info from text around each memorial ID
                for memorial_id in memorial_ids[:20]:
                    record = self._extract_from_text(content, memorial_id, search_params)
                    if record:
                        records.append(record)

        if not records:
            self.debug(f"No records extracted - returning empty list (NO_MATCH)")

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

        # Extract name - it's in the <i> tag inside the name element
        name = None
        name_elem = item.find('h2', class_='name-grave') or item.find('h3') or item.find(class_=re.compile(r'name|title'))
        if name_elem:
            # Name is in the <i> tag
            i_tag = name_elem.find('i')
            if i_tag:
                name = i_tag.get_text(' ', strip=True)
            else:
                name = name_elem.get_text(' ', strip=True)
        else:
            name = link.get_text(' ', strip=True).split('\n')[0]

        # Get all text
        item_text = item.get_text('\n', strip=True)

        # Extract full dates and years
        birth_year = None
        death_year = None
        birth_date = None
        death_date = None

        # Look for full dates in <b class="birthDeathDates">
        dates_elem = item.find('b', class_='birthDeathDates')
        if dates_elem:
            dates_text = dates_elem.get_text(strip=True)
            # Format: "15 Aug 1871 – 25 Oct 1899" or "1879 – 1968"
            dates_match = re.search(r'(\d{1,2}\s+\w+\s+)?(\d{4})\s*[–-]\s*(\d{1,2}\s+\w+\s+)?(\d{4})', dates_text)
            if dates_match:
                birth_year = int(dates_match.group(2))
                death_year = int(dates_match.group(4))
                if dates_match.group(1):  # Has full birth date
                    birth_date = f"{dates_match.group(1).strip()} {birth_year}"
                if dates_match.group(3):  # Has full death date
                    death_date = f"{dates_match.group(3).strip()} {death_year}"

        # Fallback to text extraction
        if not birth_year:
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

        # Extract photo URL
        photo_url = None
        img = item.find('img')
        if img and img.get('src'):
            photo_url = img['src']

        # Extract cemetery and location
        lines = [line.strip() for line in item_text.split('\n') if line.strip()]

        cemetery = None
        location_parts = []

        # Find cemetery
        for i, line in enumerate(lines):
            if any(word in line for word in ['Cemetery', 'Churchyard', 'Memorial', 'Gardens', 'Burial']):
                cemetery = line
                # Location is typically the next few lines after cemetery
                # Collect lines until we hit "Plot info:" or other metadata
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j]
                    if any(skip in next_line for skip in ['Plot info:', 'Memorial', 'Flowers', 'grave photo']):
                        break
                    if next_line and not next_line.isdigit():
                        location_parts.append(next_line)
                break

        # Combine location parts, clean up commas
        location = ', '.join(part.rstrip(',') for part in location_parts if part).strip()

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_date': birth_date,
            'death_date': death_date,
            'birth_place': location,
            'death_place': location,
            'cemetery': cemetery,
            'photo_url': photo_url,
            'url': url,
            'memorial_id': memorial_id,
            'source': self.source_name
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _extract_from_text(self, content: str, memorial_id: str, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic record info from text when HTML parsing fails"""
        # Build basic record with memorial ID
        url = f"https://www.findagrave.com/memorial/{memorial_id}"

        # Try to extract name near the memorial ID
        # Look for pattern like "Name\n/memorial/12345"
        pattern = rf'([A-Z][a-zA-Z\s]+)\s*/memorial/{memorial_id}'
        name_match = re.search(pattern, content)
        name = name_match.group(1).strip() if name_match else None

        # Try to find dates near the memorial ID
        # Look within ~200 chars of memorial ID
        memorial_pos = content.find(f'/memorial/{memorial_id}')
        if memorial_pos > 0:
            context = content[max(0, memorial_pos-200):memorial_pos+200]
            # Find years
            year_matches = re.findall(r'\b(1[7-9]\d{2}|20[0-2]\d)\b', context)
            birth_year = int(year_matches[0]) if year_matches else None
            death_year = int(year_matches[1]) if len(year_matches) > 1 else None
        else:
            birth_year = None
            death_year = None

        if not name:
            return None

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
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

