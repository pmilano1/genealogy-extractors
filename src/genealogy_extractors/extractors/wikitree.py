"""
WikiTree Record Extractor
Parses WikiTree API JSON responses
"""

import json
import re
from typing import List, Dict, Any
from .base import BaseRecordExtractor


class WikiTreeExtractor(BaseRecordExtractor):
    """Extract records from WikiTree API JSON responses"""
    
    def __init__(self):
        super().__init__("WikiTree")
    
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual records from WikiTree API JSON
        
        WikiTree API structure:
        - Returns JSON array with matches
        - Each match has: Id, Name, FirstName, LastName, BirthDate, DeathDate
        - URL pattern: https://www.wikitree.com/wiki/{Name}
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        
        records = []
        
        # WikiTree API returns array with first element containing results
        if isinstance(data, list) and len(data) > 0:
            result = data[0]
            matches = result.get('matches', [])
            
            for match in matches[:20]:  # Top 20 results
                try:
                    record = self._extract_person(match, search_params)
                    if record:
                        records.append(record)
                except Exception:
                    continue
        
        return records
    
    def _extract_person(self, match: Dict[str, Any], search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single WikiTree person

        WikiTree API fields:
        - Id: WikiTree internal ID
        - Name: WikiTree profile name (e.g., "Smith-269952")
        - FirstName, LastName, MiddleName
        - BirthDate, DeathDate (format: YYYY-MM-DD or YYYY-00-00)
        - BirthLocation, DeathLocation
        - Father, Mother (WikiTree IDs)
        """

        # Extract name
        first_name = match.get('FirstName', '')
        middle_name = match.get('MiddleName', '')
        last_name = match.get('LastName', '')

        # If LastName not provided, extract from Name field (format: "Smith-269952")
        if not last_name:
            wiki_name = match.get('Name', '')
            if wiki_name and '-' in wiki_name:
                last_name = wiki_name.split('-')[0]

        # Build full name
        name_parts = [first_name, middle_name, last_name]
        name = ' '.join(p for p in name_parts if p).strip()

        # Extract birth year and date
        birth_year = None
        birth_date_raw = match.get('BirthDate', '')
        birth_date = None
        if birth_date_raw and birth_date_raw != '0000-00-00':
            # Format: YYYY-MM-DD or YYYY-00-00
            year_match = re.search(r'^(\d{4})', birth_date_raw)
            if year_match:
                birth_year = int(year_match.group(1))
            # Store full date if not just year
            if not birth_date_raw.endswith('-00-00'):
                birth_date = birth_date_raw

        # Extract death year and date
        death_year = None
        death_date_raw = match.get('DeathDate', '')
        death_date = None
        if death_date_raw and death_date_raw != '0000-00-00':
            year_match = re.search(r'^(\d{4})', death_date_raw)
            if year_match:
                death_year = int(year_match.group(1))
            if not death_date_raw.endswith('-00-00'):
                death_date = death_date_raw

        # Extract locations
        birth_place = match.get('BirthLocation') or None
        death_place = match.get('DeathLocation') or None

        # Build URL
        wiki_name = match.get('Name', '')
        url = f"https://www.wikitree.com/wiki/{wiki_name}" if wiki_name else None

        record = {
            'name': name,
            'birth_year': birth_year,
            'death_year': death_year,
            'birth_date': birth_date,
            'death_date': death_date,
            'birth_place': birth_place,
            'death_place': death_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'wiki_id': match.get('Id'),
                'wiki_name': wiki_name,
                'father_id': match.get('Father'),
                'mother_id': match.get('Mother')
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if WikiTree API response has results"""
        try:
            data = json.loads(content)
            if isinstance(data, list) and len(data) > 0:
                result = data[0]
                total = result.get('total', 0)
                return total > 0
        except (json.JSONDecodeError, KeyError, IndexError):
            pass
        
        return False

