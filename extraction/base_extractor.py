"""
Base Record Extractor
Abstract base class for all source-specific extractors
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import re
import sys
import os

# Add parent directory to path for debug_log import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from debug_log import debug as _debug, warn as _warn, error as _error, is_verbose


class BaseRecordExtractor(ABC):
    """Abstract base class for record extraction from search results"""

    def __init__(self, source_name: str):
        self.source_name = source_name

    def debug(self, message: str):
        """Print debug message (only in verbose mode)."""
        _debug(self.source_name, message)

    def warn(self, message: str):
        """Print warning message."""
        _warn(self.source_name, message)

    def error(self, message: str):
        """Print error message."""
        _error(self.source_name, message)
    
    @abstractmethod
    def extract_records(self, content: str, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract structured records from HTML content
        
        Args:
            content: HTML content from search results page
            search_params: Original search parameters (surname, given_name, location, year_min, year_max)
        
        Returns:
            List of records, each containing:
            - name: Full name extracted from record
            - birth_year: Birth year (int or None)
            - birth_place: Birth place (str or None)
            - url: URL to the specific record
            - match_score: Confidence score 0-100
            - raw_data: Optional dict with additional extracted fields
        """
        pass
    
    def extract_with_fallback(self, content: str, search_params: Dict[str, Any], 
                              url: str) -> List[Dict[str, Any]]:
        """Extract records with graceful degradation if parser fails
        
        Args:
            content: HTML content
            search_params: Search parameters
            url: URL of the search results page
        
        Returns:
            List of extracted records, or URL-only fallback if extraction fails
        """
        try:
            records = self.extract_records(content, search_params)
            
            # Validate extraction worked
            if len(records) == 0 and self._has_results_indicator(content):
                # Page has results but parser failed to extract them
                self._log_parser_failure("Parser returned 0 records but page has results")
                return self._create_fallback_record(url, "PARSE_FAILED")
            
            return records
        
        except Exception as e:
            # Parser broke completely
            self._log_parser_failure(f"Parser exception: {str(e)}")
            return self._create_fallback_record(url, "PARSE_ERROR")
    
    def _has_results_indicator(self, content: str) -> bool:
        """Check if page content indicates results are present
        
        Override this in subclasses to detect source-specific result indicators
        """
        # Generic check for common result indicators
        indicators = [
            r'\d+\s+results?',
            r'\d+\s+résultats?',
            r'\d+\s+risultati',
            'search results',
            'showing results'
        ]
        
        for pattern in indicators:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _create_fallback_record(self, url: str, error_type: str) -> List[Dict[str, Any]]:
        """Create fallback record when parser fails"""
        return [{
            'name': error_type,
            'birth_year': None,
            'birth_place': None,
            'url': url,
            'match_score': 50,  # Medium confidence - needs manual review
            'source': self.source_name,
            'extraction_error': error_type
        }]
    
    def _log_parser_failure(self, message: str):
        """Log parser failure for maintenance tracking"""
        self.warn(f"PARSER FAILURE: {message}")
    
    def calculate_match_score(self, record: Dict[str, Any], search_params: Dict[str, Any]) -> int:
        """Calculate match confidence score (0-100)

        Scoring philosophy:
        - Start at 50 (neutral) - a record was found
        - Add points for matches, subtract for mismatches
        - Don't penalize missing data in search params
        - Bonus for rich data (parents, death info, etc.)

        Args:
            record: Extracted record data
            search_params: Original search parameters

        Returns:
            Match score 0-100
        """
        score = 50  # Start neutral - we found something

        name = (record.get('name') or '').lower()

        # SURNAME MATCH (most important) - up to +25
        surname = (search_params.get('surname') or '').lower()
        if surname and name:
            if surname in name:
                score += 25  # Exact substring match
            elif self._levenshtein_ratio(surname, self._extract_surname(name)) > 0.8:
                score += 15  # Close fuzzy match
            elif self._levenshtein_ratio(surname, name) > 0.5:
                score += 5   # Partial match

        # GIVEN NAME MATCH - up to +15
        given = (search_params.get('given_name') or '').lower()
        if given and name:
            if given in name:
                score += 15  # Exact match
            elif len(given) >= 1 and len(name) >= 1:
                # Check for initial match (N = Noel)
                name_parts = name.split()
                if name_parts and given[0] == name_parts[0][0]:
                    score += 10  # Initial matches
                elif self._levenshtein_ratio(given, name) > 0.7:
                    score += 10  # Close fuzzy match

        # BIRTH YEAR MATCH - up to +20
        search_year = search_params.get('birth_year') or search_params.get('year_min')
        record_year = record.get('birth_year')
        if search_year and record_year:
            diff = abs(int(search_year) - int(record_year))
            if diff == 0:
                score += 20
            elif diff <= 2:
                score += 15
            elif diff <= 5:
                score += 10
            elif diff <= 10:
                score += 5
            elif diff > 20:
                score -= 10  # Penalize large year differences

        # LOCATION MATCH (bonus only, no penalty for missing) - up to +10
        search_loc = (search_params.get('location') or '').lower()
        record_loc = (record.get('birth_place') or '').lower()
        if search_loc and record_loc:
            if search_loc in record_loc or record_loc in search_loc:
                score += 10
            elif self._levenshtein_ratio(search_loc, record_loc) > 0.6:
                score += 5

        # BONUS for rich data - up to +10
        raw = record.get('raw_data') or {}
        if record.get('death_year'):
            score += 2
        if record.get('death_place'):
            score += 2
        if raw.get('father') or raw.get('mother') or raw.get('parents'):
            score += 4
        if record.get('url'):
            score += 2

        return max(0, min(score, 100))

    def _extract_surname(self, name: str) -> str:
        """Extract likely surname from full name (last word, or UPPERCASE word)"""
        if not name:
            return ''
        parts = name.split()
        # Check for UPPERCASE surname (common in European records)
        for part in parts:
            if part.isupper() and len(part) > 1:
                return part.lower()
        # Default to last word
        return parts[-1] if parts else ''

    def _levenshtein_ratio(self, s1: str, s2: str) -> float:
        """Calculate Levenshtein similarity ratio (0.0 to 1.0)"""
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0

        # Simple Levenshtein distance
        len1, len2 = len(s1), len(s2)
        if len1 < len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1

        # Use only two rows of the matrix
        prev_row = list(range(len2 + 1))
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row

        distance = prev_row[len2]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)

