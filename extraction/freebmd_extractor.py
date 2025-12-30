"""
FreeBMD Record Extractor
Parses FreeBMD (UK Birth, Marriage, Death records) search results
"""

import re
from typing import List, Dict, Any
from urllib.parse import unquote
from .base_extractor import BaseRecordExtractor


class FreeBMDExtractor(BaseRecordExtractor):
    """Extract records from FreeBMD search results"""

    def __init__(self):
        super().__init__("FreeBMD")

    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract BMD records from FreeBMD results

        FreeBMD stores data in a JavaScript array called searchData.
        Format: "type;surname;given;mother;flag;district;volume;page;reference"

        Type codes: 43=Birth confirmed, 41=Birth unconfirmed
        Surname/given are only on first row of a group - subsequent rows inherit them.
        """
        records = []

        # Extract the searchData JavaScript array
        search_data_match = re.search(
            r'var\s+searchData\s*=\s*new\s+Array\s*\((.*?)\);',
            content,
            re.DOTALL
        )

        if not search_data_match:
            return []

        # Parse the array entries
        data_str = search_data_match.group(1)

        # Extract individual entries (quoted strings)
        entries = re.findall(r'"([^"]*)"', data_str)

        if not entries:
            return []

        # First entry is header: " ;quarter;type;year"
        header = entries[0].split(';')
        current_year = None
        if len(header) >= 4:
            try:
                current_year = int(header[3])
            except ValueError:
                pass

        # Track current surname/given for inherited values
        current_surname = ''
        current_given = ''

        for entry in entries[1:50]:  # Process up to 50 records
            try:
                record = self._parse_entry(entry, current_surname, current_given,
                                          current_year, search_params)
                if record:
                    # Update current values if this entry has them
                    if record['raw_data'].get('surname'):
                        current_surname = record['raw_data']['surname']
                    if record['raw_data'].get('given_name'):
                        current_given = record['raw_data']['given_name']
                    records.append(record)
            except Exception:
                continue

        return records

    def _parse_entry(self, entry: str, current_surname: str, current_given: str,
                     year: int, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single searchData entry

        Format: "type;surname;given;mother;flag;district;volume;page;reference"
        """
        parts = entry.split(';')
        if len(parts) < 8:
            return None

        type_code = parts[0]
        surname = parts[1].strip() if parts[1].strip() else current_surname
        given_name = parts[2].strip() if parts[2].strip() else current_given
        mother = parts[3].strip() if len(parts) > 3 else ''
        # parts[4] is a flag
        district = unquote(parts[5]) if len(parts) > 5 else ''
        volume = parts[6] if len(parts) > 6 else ''
        page = parts[7] if len(parts) > 7 else ''
        reference = parts[8] if len(parts) > 8 else ''

        # Skip if no name
        if not surname and not given_name:
            return None

        # Build name
        name = f"{given_name} {surname}".strip()

        # Determine record type
        record_type = 'birth'
        if type_code in ['43', '41']:
            record_type = 'birth'
        elif type_code in ['44', '42']:
            record_type = 'death'
        elif type_code in ['45', '46']:
            record_type = 'marriage'

        # Build info URL
        info_url = f"https://www.freebmd.org.uk/cgi/information.pl?r={reference}"

        record = {
            'name': name,
            'birth_year': year,
            'birth_place': district,
            'url': info_url,
            'source': self.source_name,
            'raw_data': {
                'district': district,
                'surname': surname,
                'given_name': given_name,
                'mother': mother,
                'volume': volume,
                'page': page,
                'reference': reference,
                'type': record_type,
                'confirmed': type_code in ['43', '44', '45']
            }
        }

        record['match_score'] = self.calculate_match_score(record, search_params)
        return record

    def _has_results_indicator(self, content: str) -> bool:
        """Check if FreeBMD page has results"""
        return 'var searchData' in content

