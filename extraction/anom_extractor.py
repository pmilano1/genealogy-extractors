"""
ANOM (Archives Nationales d'Outre-Mer) Record Extractor

Handles two name-searchable databases:
1. BAGNE (Penal Colony Records) - Full text extraction
2. MILITARY MATRICULES - Search results + image URLs

Coverage:
- Bagne: French Guiana, New Caledonia convicts (includes Commune of Paris deportees)
- Military: Algeria 1866-1924, Guyane 1890-1920, Réunion 1884-1918, Madagascar, etc.
"""

import re
from typing import List, Dict, Any, Optional
from urllib.parse import quote, urlencode
from bs4 import BeautifulSoup
from .base_extractor import BaseRecordExtractor


class ANOMExtractor(BaseRecordExtractor):
    """Extract records from ANOM search results (Bagne and Military databases)"""

    BASE_URL = "https://recherche-anom.culture.gouv.fr"
    MILITARY_URL = "http://anom.archivesnationales.culture.gouv.fr/regmatmil"

    # Military territories available for search
    MILITARY_TERRITORIES = [
        'Afrique', 'Algerie', 'Comores', 'Côte française des Somalis',
        'Guyane', 'Inde-Indochine', 'La Réunion', 'Madagascar',
        'Nouvelle-Calédonie', 'Polynésie', 'Saint-Pierre', 'Saint-Pierre-et-Miquelon'
    ]

    def __init__(self):
        super().__init__("ANOM")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from ANOM content

        Automatically detects database type (Bagne vs Military) and extracts accordingly.
        """
        records = []
        soup = BeautifulSoup(content, 'html.parser')

        # Detect which database we're parsing
        # Note: Check bagne FIRST because bagne pages may contain "Registres matricules" text
        # The military site uses anom.archivesnationales.culture.gouv.fr/regmatmil
        # The bagne site uses recherche-anom.culture.gouv.fr with basebagne
        if 'type-notice-basebagne' in content or 'basebagne' in content:
            records = self._extract_bagne_records(soup, content, search_params)
        elif 'anom.archivesnationales.culture.gouv.fr/regmatmil' in content:
            records = self._extract_military_records(soup, search_params)
        else:
            # Try bagne first, then military
            records = self._extract_bagne_records(soup, content, search_params)
            if not records:
                records = self._extract_military_records(soup, search_params)

        if not records:
            self.debug(f"No records extracted - returning empty list (NO_MATCH)")

        return records

    def _extract_military_records(self, soup: BeautifulSoup, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from Military Matricules search results"""
        records = []

        # Find result table rows (have onclick handlers)
        result_rows = soup.find_all('tr', class_=re.compile(r'(pair|impair)'))
        result_rows = [r for r in result_rows if r.get('onclick')]

        if not result_rows:
            return records

        self.debug(f"Found {len(result_rows)} military result rows")

        for row in result_rows[:50]:  # Limit to top 50
            try:
                record = self._extract_military_row(row, search_params)
                if record:
                    records.append(record)
            except Exception as e:
                self.debug(f"Failed to extract military row: {e}")
                continue

        return records

    def _extract_military_row(self, row, search_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract data from a military matricule result row"""
        # Get onclick URL for detail page
        onclick = row.get('onclick', '')
        detail_url = None
        if 'osd.php?clef=' in onclick:
            match = re.search(r"osd\.php\?clef=([^'\"]+)", onclick)
            if match:
                detail_url = f"{self.MILITARY_URL}/osd.php?clef={match.group(1)}"

        # Get title attribute which contains birth info
        title = row.get('title', '')
        birth_date = None
        birth_year = None
        birth_place = None
        birth_dept = None

        # Parse title: "Date de naissance : 1860-02-20\nDépartement / territoire de naissance : Alger"
        birth_match = re.search(r'Date de naissance\s*:\s*(\d{4})-(\d{2})-(\d{2})', title)
        if birth_match:
            birth_year = int(birth_match.group(1))
            birth_date = f"{birth_match.group(1)}-{birth_match.group(2)}-{birth_match.group(3)}"

        dept_match = re.search(r'territoire de naissance\s*:\s*(.+)', title)
        if dept_match:
            birth_dept = dept_match.group(1).strip()

        # Extract cells
        cells = row.find_all('td')
        if len(cells) < 6:
            return None

        # Cells: [number, access_icon, nom, prenoms, classe, matricule, territoire, bureau]
        surname = cells[2].get_text(strip=True) if len(cells) > 2 else None
        given_names = cells[3].get_text(strip=True) if len(cells) > 3 else None
        classe = cells[4].get_text(strip=True) if len(cells) > 4 else None
        matricule = cells[5].get_text(strip=True) if len(cells) > 5 else None
        territoire = cells[6].get_text(strip=True) if len(cells) > 6 else None
        bureau = cells[7].get_text(strip=True) if len(cells) > 7 else None

        if not surname:
            return None

        # Birth place comes from the title attribute (département/territoire de naissance)
        # The detail URL is too complex to parse reliably due to name encoding
        birth_place = birth_dept  # Use the département as birth place

        name = f"{surname}, {given_names}" if given_names else surname

        record = {
            'name': name,
            'surname': surname,
            'given_names': given_names,
            'birth_year': birth_year,
            'birth_date': birth_date,
            'birth_place': birth_place,
            'birth_department': birth_dept,
            'recruitment_class': int(classe) if classe and classe.isdigit() else None,
            'matricule': matricule,
            'territory': territoire,
            'recruitment_bureau': bureau,
            'detail_url': detail_url,
            'source': self.source_name,
            'database': 'military_matricules',
            'note': 'Detail page contains scanned image with parent names, address, profession'
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _extract_bagne_records(self, soup: BeautifulSoup, content: str,
                                search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract records from Bagne (penal colony) search results"""
        records = []

        # Find result rows - classes are ['arc_impair', 'type-notice-basebagne']
        # BeautifulSoup matches regex against each class individually
        result_rows = soup.find_all('tr', class_=re.compile(r'type-notice'))

        if result_rows:
            self.debug(f"Found {len(result_rows)} bagne result rows")
            for row in result_rows[:30]:
                try:
                    record = self._extract_bagne_row(row, search_params)
                    if record:
                        records.append(record)
                except Exception as e:
                    self.debug(f"Failed to extract bagne row: {e}")
                    continue
        else:
            # Fallback: look for ARK IDs
            ark_ids = re.findall(r'ark:/61561/(\d+)', content)
            if ark_ids:
                self.debug(f"Found {len(set(ark_ids))} ARK IDs in text")
                for ark_id in list(set(ark_ids))[:20]:
                    record = self._extract_from_text(content, ark_id, search_params)
                    if record:
                        records.append(record)

        return records
    
    def _extract_bagne_row(self, row, search_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract data from a Bagne result row"""
        # Extract name from unittitle
        name_elem = row.find('span', class_='unittitle')
        name = name_elem.get_text(strip=True) if name_elem else None

        if not name:
            return None

        # Extract ARK identifier and build URL
        ark_link = row.find('a', href=re.compile(r'/ark:/'))
        ark_id = None
        url = None
        if ark_link:
            href = ark_link.get('href')
            ark_match = re.search(r'ark:/61561/(\d+)', href)
            if ark_match:
                ark_id = ark_match.group(1)
                url = f"{self.BASE_URL}/ark:/61561/{ark_id}"

        # Extract all field items
        items = row.find_all('div', class_='items')
        fields = {}
        for item in items:
            label = item.find('strong', class_='arc_libelle_strong')
            if label:
                # Extract key - label ends with &nbsp;: which shows as \xa0:
                key = label.get_text(strip=True).replace('\xa0', ' ').rstrip(' :').strip()
                p_elem = item.find('p', class_='arc_firstp')
                if p_elem:
                    fields[key] = p_elem.get_text(strip=True)
                else:
                    # For items without <p>, extract text nodes after the label
                    # Get all text from item, then strip the key pattern from start
                    full_text = item.get_text(strip=True)
                    # Remove key pattern "Key :" or "Key\xa0:" from start
                    for pattern in [f"{key}\xa0:", f"{key} :", f"{key}:"]:
                        if full_text.startswith(pattern):
                            full_text = full_text[len(pattern):]
                            break
                    fields[key] = full_text.strip()

        # Extract condemnation year
        condemnation_year = None
        if 'Condamné en' in fields:
            year_match = re.search(r'(\d{4})', fields['Condamné en'])
            if year_match:
                condemnation_year = int(year_match.group(1))

        # Extract death info from observations
        death_year = None
        death_date = None
        observations = fields.get('Observations complémentaires', '')
        death_match = re.search(r'Décédé[e]?\s+le\s+(\d{1,2}\s+\w+\s+(\d{4}))', observations)
        if death_match:
            death_date = death_match.group(1)
            death_year = int(death_match.group(2))

        # Extract image URL if present
        image_url = None
        img = row.find('img')
        if img and img.get('src'):
            image_url = img['src']

        territory = fields.get('Territoire de détention', '').strip('.')

        record = {
            'name': name,
            'birth_year': None,
            'death_year': death_year,
            'death_date': death_date,
            'birth_place': None,
            'condemnation_year': condemnation_year,
            'territory': territory,
            'cote': fields.get('Cote du dossier'),
            'matricule': fields.get('Numéro de matricule'),
            'sex': fields.get('Sexe'),
            'jurisdiction': fields.get('Juridiction de condamnation'),
            'observations': observations,
            'ark_id': ark_id,
            'url': url,
            'image_url': image_url,
            'source': self.source_name,
            'database': 'bagne',
            'raw_data': fields
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _extract_from_text(self, content: str, ark_id: str,
                           search_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract basic record from text when HTML parsing fails"""
        url = f"{self.BASE_URL}/ark:/61561/{ark_id}"

        # Look for name near ARK ID
        context_start = max(0, content.find(ark_id) - 500)
        context_end = min(len(content), content.find(ark_id) + 500)
        context = content[context_start:context_end]

        # Try to find name pattern
        name_match = re.search(r'unittitle["\']?>([^<]+)<', context)
        name = name_match.group(1).strip() if name_match else None

        if not name:
            return None

        record = {
            'name': name,
            'url': url,
            'ark_id': ark_id,
            'source': self.source_name,
            'database': 'bagne'
        }
        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _has_results_indicator(self, content: str) -> bool:
        """Check if ANOM page has results"""
        indicators = [
            r'\d+\s+réponses?',
            r'\d+\s+résultats?',
            r'ark:/61561/',
            r'type-notice',
            r'inventaires?'
        ]

        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    @staticmethod
    def build_bagne_search_url(surname: str = None, given_name: str = None,
                                year_start: int = None, year_end: int = None,
                                territory: str = None) -> str:
        """Build ANOM Bagne database search URL

        Args:
            surname: Surname to search
            given_name: First name to search
            year_start: Start of conviction year range
            year_end: End of conviction year range
            territory: Territory of detention (Guyane française, Nouvelle-Calédonie, etc.)

        Returns:
            Complete search URL
        """
        base = "https://recherche-anom.culture.gouv.fr/archive/recherche/basebagne/n:174"
        params = []

        if surname:
            params.append(f"RECH_nom={surname}")
        if given_name:
            params.append(f"RECH_abstract={given_name}")
        if year_start:
            params.append(f"RECH_date_debut={year_start}")
        if year_end:
            params.append(f"RECH_date_fin={year_end}")
        if territory:
            params.append(f"RECH_Territoire={territory}")

        if params:
            return f"{base}?{'&'.join(params)}"
        return base

    @staticmethod
    def build_military_search_url(surname: str = None, given_names: str = None,
                                   territory: str = None, bureau: str = None,
                                   year_start: int = None, year_end: int = None) -> str:
        """Build ANOM Military Matricules search URL

        NOTE: This URL is for reference only. The actual search requires
        filling the form and clicking the search button via browser automation.

        Args:
            surname: Surname to search
            given_names: First name(s) to search
            territory: Territory (Algerie, Guyane, Réunion, etc.)
            bureau: Recruitment bureau
            year_start: Start of recruitment class year range
            year_end: End of recruitment class year range

        Returns:
            Base URL (form must be submitted via browser)
        """
        # Military search requires form submission - URL params don't work
        return "http://anom.archivesnationales.culture.gouv.fr/regmatmil/"

    @staticmethod
    def get_military_search_params(surname: str = None, given_names: str = None,
                                    territory: str = None, year_start: int = None,
                                    year_end: int = None) -> Dict[str, Any]:
        """Get parameters for military matricule search (for browser automation)

        Args:
            surname: Surname to search
            given_names: First name(s) to search
            territory: Territory (Algerie, Guyane, etc.)
            year_start: Start of recruitment class year range
            year_end: End of recruitment class year range

        Returns:
            Dict of form field IDs and values to fill
        """
        params = {}
        if surname:
            params['nom'] = surname
        if given_names:
            params['prenom'] = given_names
        if territory:
            params['territoire'] = territory
        if year_start:
            params['from'] = str(year_start)
        if year_end:
            params['to'] = str(year_end)
        return params


# Example usage and testing
if __name__ == "__main__":
    # Test Bagne URL building
    url = ANOMExtractor.build_bagne_search_url(
        surname="Dupont",
        year_start=1850,
        year_end=1900
    )
    print(f"Bagne URL: {url}")

    # Test Military search params
    params = ANOMExtractor.get_military_search_params(
        surname="Martin",
        territory="Algerie",
        year_start=1880,
        year_end=1910
    )
    print(f"Military search params: {params}")
    print(f"Military URL: {ANOMExtractor.build_military_search_url()}")
