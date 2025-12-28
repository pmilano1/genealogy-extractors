"""
WikiTree Record Extractor
Parses WikiTree API JSON responses
"""

import json
import re
from typing import List, Dict, Any
from .base_extractor import BaseRecordExtractor


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
        """Extract data from a single WikiTree person"""

        # Extract name
        first_name = match.get('FirstName', '')
        last_name = match.get('LastName', '')

        # If LastName not provided, extract from Name field (format: "Smith-269952")
        if not last_name:
            wiki_name = match.get('Name', '')
            if wiki_name and '-' in wiki_name:
                last_name = wiki_name.split('-')[0]

        name = f"{first_name} {last_name}".strip()
        
        # Extract birth year
        birth_year = None
        birth_date = match.get('BirthDate', '')
        if birth_date:
            year_match = re.search(r'\b(1[7-9]\d{2}|20\d{2})\b', birth_date)
            if year_match:
                birth_year = int(year_match.group(1))
        
        # Extract location
        birth_place = match.get('BirthLocation', None)
        
        # Build URL
        wiki_name = match.get('Name', '')
        url = f"https://www.wikitree.com/wiki/{wiki_name}" if wiki_name else None
        
        record = {
            'name': name,
            'birth_year': birth_year,
            'birth_place': birth_place,
            'url': url,
            'source': self.source_name,
            'raw_data': {
                'wiki_id': match.get('Id'),
                'death_date': match.get('DeathDate')
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

