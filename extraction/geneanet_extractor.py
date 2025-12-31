"""
Geneanet Record Extractor
Parses Geneanet search results (French genealogy site)
Enhanced to capture parents, spouse, marriage date, and image URLs
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class GeneanetExtractor(BaseRecordExtractor):
    """Extract records from Geneanet search results"""

    def __init__(self):
        super().__init__("Geneanet")

    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual records from Geneanet results

        Geneanet structure:
        - Search results in <a class="ligne-resultat"> elements
        - Each has: name, birth/death dates, location, family tree link
        - Tooltips contain: full dates, parents, marriage info
        - URL pattern: https://gw.geneanet.org/...
        """
        soup = BeautifulSoup(content, 'html.parser')
        records = []

        # Find all result rows (ligne-resultat)
        result_items = soup.find_all('a', class_='ligne-resultat')

        self.debug(f"Found {len(result_items)} ligne-resultat items in Geneanet HTML")

        for item in result_items[:20]:  # Limit to first 20 results
            try:
                record = self._extract_individual(item, soup, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                self.debug(f"Failed to extract individual: {e}")
                continue

        return records
    
    def _extract_individual(self, element, soup: BeautifulSoup, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single Geneanet individual

        Structure:
        <a class="ligne-resultat" href="URL" data-id-es="...">
          <div class="image-resultat">
            <div class="vignette"><img src="..."/></div>
          </div>
          <div class="info-resultat">
            <div class="content-individu">
              <p id="a-tooltip-..." class="text-large">SURNAME Given_Name</p>
              <p>Spouse: NAME (YEAR)</p>
            </div>
            <div class="content-periode">
              <p><span class="text-light">Birth</span> <span class="text-large">YEAR</span></p>
            </div>
            <div class="content-lieu">
              <p><span class="title-lieu">LOCATION</span></p>
            </div>
          </div>
        </a>

        Tooltip (in separate div with matching id):
        <div id="drop-tooltip-...">
          <table><tr><td>Birth</td><td>:</td><td>January 03, 1879</td></tr></table>
          <div>Parents : SURNAME Given (father), SURNAME Given (mother)</div>
        </div>
        """

        # Extract URL (element itself is the <a> tag)
        url = element.get('href', '')
        if not url:
            return None

        # Extract name from content-individu section
        name = ""
        name_elem = element.find('p', class_=re.compile(r'text-large'))
        tooltip_id = None
        if name_elem:
            # Clean up extra whitespace between surname and given name
            name = ' '.join(name_elem.get_text(strip=True).split())
            # Get tooltip ID for additional info
            tooltip_id = name_elem.get('data-dropdown-id')

        # Extract image URL
        image_url = None
        img = element.find('img')
        if img and img.get('src'):
            image_url = img['src']

        # Extract birth and death years from content-periode section
        birth_year = None
        death_year = None
        periode_div = element.find('div', class_='content-periode')
        if periode_div:
            # Find Birth year
            birth_p = periode_div.find('span', string='Birth')
            if birth_p and birth_p.parent:
                year_span = birth_p.parent.find('span', class_='text-large')
                if year_span:
                    try:
                        birth_year = int(year_span.get_text(strip=True))
                    except ValueError:
                        pass

            # Find Death year
            death_p = periode_div.find('span', string='Death')
            if death_p and death_p.parent:
                year_span = death_p.parent.find('span', class_='text-large')
                if year_span:
                    try:
                        death_year = int(year_span.get_text(strip=True))
                    except ValueError:
                        pass

        # Extract location from content-lieu section
        birth_place = None
        lieu_div = element.find('div', class_='content-lieu')
        if lieu_div:
            lieu_span = lieu_div.find('span', class_='title-lieu')
            if lieu_span:
                birth_place = lieu_span.get_text(strip=True)

        # Extract spouse info if present
        spouse = None
        marriage_year = None
        individu_div = element.find('div', class_='content-individu')
        if individu_div:
            spouse_span = individu_div.find('span', string='Spouse')
            if spouse_span and spouse_span.parent:
                spouse_span_val = spouse_span.parent.find('span', class_='text-large')
                if spouse_span_val:
                    spouse_text = spouse_span_val.get_text(strip=True)
                    # Extract marriage year from "(1907)" pattern
                    year_match = re.search(r'\((\d{4})\)', spouse_text)
                    if year_match:
                        marriage_year = int(year_match.group(1))
                        # Remove year from spouse name
                        spouse = re.sub(r'\s*\(\d{4}\)\s*', '', spouse_text).strip()
                    else:
                        spouse = spouse_text

        # Try to get additional info from tooltip (parents, full dates)
        father = None
        mother = None
        birth_date = None
        death_date = None
        marriage_date = None

        if tooltip_id:
            tooltip = soup.find('div', id=tooltip_id)
            if tooltip:
                # Extract full dates from table
                for row in tooltip.find_all('tr', class_='top-infos'):
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        label_text = cells[0].get_text(strip=True).lower()
                        value_text = cells[2].get_text(strip=True)
                        if label_text == 'birth':
                            birth_date = value_text
                        elif label_text == 'death':
                            death_date = value_text
                        elif label_text == 'marriage':
                            marriage_date = value_text

                # Extract parents - look for icon-search-homme (father) and icon-search-femme (mother)
                # These are in the tooltip, not in the main result
                father_p = tooltip.find('p', class_=re.compile(r'icon-search-homme'))
                if father_p:
                    father = father_p.get_text(strip=True)

                mother_p = tooltip.find('p', class_=re.compile(r'icon-search-femme'))
                if mother_p:
                    mother = mother_p.get_text(strip=True)

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_date': birth_date,
            'death_date': death_date,
            'birth_place': birth_place,
            'url': url,
            'image_url': image_url,
            'source': self.source_name,
            'raw_data': {
                'spouse': spouse,
                'marriage_year': marriage_year,
                'marriage_date': marriage_date,
                'father': father,
                'mother': mother
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if Geneanet page has results"""
        indicators = [
            r'\d+\s+résultats?',
            r'\d+\s+results?',
            '/individu/',
            'search results'
        ]
        
        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False

