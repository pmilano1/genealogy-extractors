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

        self.debug(f"Found {len(person_rows)} person rows in FamilySearch HTML")

        for row in person_rows[:20]:
            try:
                record = self._extract_person(row, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                self.debug(f"Failed to extract person: {e}")
                continue

        return records
    
    def _extract_person(self, row, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single FamilySearch result row

        FamilySearch can have multiple columns with different event types:
        - Birth/Baptism/Christening
        - Death/Burial
        - Marriage
        - Parents
        - Spouse
        - Residence
        - Other events
        """
        # Extract ARK ID from data-testid attribute
        ark_id = row.get('data-testid', '')

        # Extract name and URL from link (class name varies)
        link = row.find('a', class_=re.compile(r'linkCss'))
        if not link:
            # Fallback: find first link in h2
            h2 = row.find('h2')
            if h2:
                link = h2.find('a')
        if not link:
            return None

        name = link.get_text(strip=True)
        url = link.get('href', '')
        if url and not url.startswith('http'):
            url = f"https://www.familysearch.org{url}"

        # Extract collection/record type from div after name
        # Structure: <h2><strong><a>Name</a></strong><br><div>Principal<br>Collection Name</div></h2>
        collection = None
        h2 = link.find_parent('h2')
        if h2:
            div_after_name = h2.find('div')
            if div_after_name:
                # Get text, split by newlines, take the last part (collection name)
                div_text = div_after_name.get_text(separator='\n', strip=True)
                lines = [l.strip() for l in div_text.split('\n') if l.strip()]
                # Skip "Principal" or similar role labels
                for line in lines:
                    if line.lower() not in ['principal', 'other', 'spouse', 'parent', 'child']:
                        collection = line
                        break

        # Initialize all data fields
        birth_year = None
        birth_place = None
        birth_date = None
        death_year = None
        death_place = None
        death_date = None
        marriage_year = None
        marriage_place = None
        residence = None
        father = None
        mother = None
        spouse = None

        # Find all <td> cells and extract data by event type
        # Skip the first cell (contains name/collection) and last cell (contains links)
        cells = row.find_all('td')
        for i, cell in enumerate(cells):
            # Skip first cell (name) and cells with only hidden content
            if i == 0:
                continue

            # Check if cell has a <strong> tag indicating event type
            strong_tags = cell.find_all('strong')
            if not strong_tags:
                continue

            cell_text = cell.get_text(separator='\n', strip=True)

            # Parse Birth/Baptism/Christening - look for <strong>Birth</strong> etc.
            for strong in strong_tags:
                event_type = strong.get_text(strip=True)

                if any(event in event_type for event in ['Birth', 'Baptism', 'Christening']):
                    year, date, place = self._extract_event_data(cell)
                    if year and not birth_year:
                        birth_year = year
                        birth_date = date
                        birth_place = place

                # Parse Death/Burial
                elif any(event in event_type for event in ['Death', 'Burial', 'Died']):
                    year, date, place = self._extract_event_data(cell)
                    if year and not death_year:
                        death_year = year
                        death_date = date
                        death_place = place

                # Parse Marriage
                elif 'Marriage' in event_type or 'Married' in event_type:
                    year, date, place = self._extract_event_data(cell)
                    if year:
                        marriage_year = year
                        marriage_place = place

                # Parse Residence
                elif 'Residence' in event_type or 'Living' in event_type:
                    _, _, place = self._extract_event_data(cell)
                    if place:
                        residence = place

                # Parse Parents - "Parents: Janet Anderson, William Anderson"
                elif 'Parents' in event_type:
                    # Get text after the strong tag
                    parents_text = cell_text
                    # Remove labels
                    parents_text = re.sub(r'(Parents|Father|Mother)\s*:?\s*', '', parents_text)
                    parents_text = parents_text.strip()
                    if parents_text:
                        # Try to split into two parents
                        parts = re.split(r',\s*|\s+and\s+', parents_text, maxsplit=1)
                        if len(parts) == 2:
                            # Use gender detection to assign father/mother correctly
                            parent1 = parts[0].strip()
                            parent2 = parts[1].strip()
                            gender1 = self._detect_gender(parent1)
                            gender2 = self._detect_gender(parent2)

                            if gender1 == 'male' and gender2 == 'female':
                                father = parent1
                                mother = parent2
                            elif gender1 == 'female' and gender2 == 'male':
                                father = parent2
                                mother = parent1
                            else:
                                # Can't determine, use order (first=father, second=mother)
                                father = parent1
                                mother = parent2
                        elif len(parts) == 1:
                            # Only one parent listed
                            parent = parts[0].strip()
                            gender = self._detect_gender(parent)
                            if gender == 'female':
                                mother = parent
                            else:
                                father = parent

                # Parse Spouse
                elif 'Spouse' in event_type or 'Wife' in event_type or 'Husband' in event_type:
                    spouse_text = cell_text
                    spouse_text = re.sub(r'(Spouse|Wife|Husband)\s*:?\s*', '', spouse_text)
                    spouse = spouse_text.strip()

        # Extract record type from collection (Birth, Marriage, Death, Census, etc.)
        record_type = None
        if collection:
            if any(term in collection.lower() for term in ['birth', 'christening', 'baptism']):
                record_type = 'birth'
            elif any(term in collection.lower() for term in ['death', 'burial']):
                record_type = 'death'
            elif 'marriage' in collection.lower():
                record_type = 'marriage'
            elif 'census' in collection.lower():
                record_type = 'census'
            elif any(term in collection.lower() for term in ['military', 'draft', 'enlistment']):
                record_type = 'military'
            elif any(term in collection.lower() for term in ['immigration', 'passenger', 'arrival']):
                record_type = 'immigration'
            elif any(term in collection.lower() for term in ['naturalization', 'citizenship']):
                record_type = 'naturalization'

        # Extract role (Principal, Parent, Spouse, Child)
        role = None
        name_container = link.parent if link.parent else None
        if name_container:
            div_after_name = name_container.find('div')
            if div_after_name:
                text = div_after_name.get_text(strip=True)
                if 'Principal' in text:
                    role = 'principal'
                elif 'Parent' in text:
                    role = 'parent'
                elif 'Spouse' in text:
                    role = 'spouse'
                elif 'Child' in text:
                    role = 'child'

        record = {
            'name': name,
            'birth_year': birth_year,
            'birth_date': birth_date,
            'birth_place': birth_place,
            'death_year': death_year,
            'death_date': death_date,
            'death_place': death_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'ark_id': ark_id,
                'collection': collection,
                'record_type': record_type,
                'role': role,
                'marriage_year': marriage_year,
                'marriage_place': marriage_place,
                'residence': residence,
                'father': father,
                'mother': mother,
                'spouse': spouse
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _extract_event_data(self, cell) -> tuple:
        """Extract year, full date, and place from an event cell

        Returns:
            tuple: (year: int|None, date: str|None, place: str|None)
        """
        year = None
        date = None
        place = None

        cell_text = cell.get_text(separator='\n', strip=True)

        # Extract year from spans first (more reliable)
        year_spans = cell.find_all('span')
        for span in year_spans:
            span_text = span.get_text(strip=True)
            year_match = re.search(r'\b(1[5-9]\d{2}|20\d{2})\b', span_text)
            if year_match:
                year = int(year_match.group(1))
                # Check if this span has a full date
                date_match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', span_text)
                if date_match:
                    date = date_match.group(1)
                break

        # Fallback: extract year from text
        if not year:
            year_match = re.search(r'\b(1[5-9]\d{2}|20\d{2})\b', cell_text)
            if year_match:
                year = int(year_match.group(1))

        # Extract location - lines that aren't event types or dates
        lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
        event_keywords = ['Birth', 'Baptism', 'Christening', 'Death', 'Burial',
                          'Marriage', 'Married', 'Residence', 'Living', 'Parents',
                          'Father', 'Mother', 'Spouse', 'Wife', 'Husband',
                          'Birth Registration']

        for line in lines:
            # Skip event type labels
            if any(line.startswith(kw) or line == kw for kw in event_keywords):
                continue
            # Skip pure year lines
            if re.match(r'^\d{4}$', line):
                continue
            # Skip full date lines (e.g., "15 Aug 1875")
            if re.match(r'^\d{1,2}\s+\w+\s+\d{4}$', line):
                continue
            # Skip month-year lines (e.g., "September 1871")
            if re.match(r'^[A-Z][a-z]+\s+\d{4}$', line):
                continue
            # This is likely a location - should contain comma or geographic terms
            if line and (
                ',' in line or
                any(term in line.lower() for term in ['county', 'state', 'province', 'england', 'scotland', 'ireland', 'wales', 'germany', 'france', 'italy', 'canada', 'united states', 'michigan', 'illinois', 'ontario', 'kingdom'])
            ):
                place = line
                break

        return year, date, place
    
    def _detect_gender(self, name: str) -> str:
        """Detect gender from a name based on common first names

        Returns:
            'male', 'female', or 'unknown'
        """
        # Extract first name (first word before space)
        first_name = name.split()[0].lower() if name else ''

        # Common female first names (historical)
        female_names = {
            'mary', 'anna', 'anne', 'ann', 'elizabeth', 'margaret', 'sarah', 'jane',
            'catherine', 'katherine', 'kate', 'maria', 'marie', 'martha', 'ellen',
            'helen', 'emma', 'alice', 'agnes', 'janet', 'jean', 'joan', 'julia',
            'harriet', 'hannah', 'grace', 'frances', 'florence', 'dorothy', 'edith',
            'eliza', 'emily', 'eva', 'evelyn', 'fanny', 'gertrude', 'ida', 'irene',
            'isabelle', 'isabel', 'josephine', 'laura', 'lillian', 'louise', 'lucy',
            'mabel', 'mildred', 'minnie', 'nancy', 'nellie', 'olive', 'pearl',
            'rachel', 'rebecca', 'rosa', 'rose', 'ruth', 'sophia', 'susan', 'susanna',
            'virginia', 'winifred', 'annie', 'bessie', 'clara', 'cora', 'dora',
            'effie', 'ella', 'elsie', 'esther', 'ethel', 'fannie', 'flora', 'hattie',
            'henrietta', 'hilda', 'jennie', 'jessie', 'katie', 'lena', 'lottie',
            'louisa', 'lydia', 'maggie', 'mamie', 'mattie', 'maude', 'may', 'nora',
            'sadie', 'sallie', 'stella', 'theresa', 'viola', 'willie', 'sillias',
            'euphemin', 'clementine', 'euphemia', 'marion', 'olive', 'jeanne'
        }

        # Common male first names (historical)
        male_names = {
            'john', 'william', 'james', 'george', 'charles', 'thomas', 'henry',
            'robert', 'joseph', 'edward', 'frank', 'samuel', 'david', 'richard',
            'michael', 'daniel', 'peter', 'paul', 'andrew', 'benjamin', 'jacob',
            'isaac', 'abraham', 'albert', 'alfred', 'arthur', 'carl', 'clarence',
            'earl', 'ernest', 'eugene', 'frederick', 'harold', 'harry', 'herbert',
            'howard', 'hugh', 'jesse', 'lewis', 'louis', 'martin', 'matthew',
            'nathan', 'oscar', 'patrick', 'philip', 'ralph', 'raymond', 'roy',
            'stephen', 'walter', 'warren', 'wm', 'chas', 'thos', 'jas', 'jno',
            'wm.', 'chas.', 'thos.', 'jas.', 'jno.', 'alex', 'alexander'
        }

        if first_name in female_names:
            return 'female'
        elif first_name in male_names:
            return 'male'
        else:
            return 'unknown'

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

