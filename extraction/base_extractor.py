"""
Base Record Extractor
Abstract base class for all source-specific extractors
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import re


class BaseRecordExtractor(ABC):
    """Abstract base class for record extraction from search results"""
    
    def __init__(self, source_name: str):
        self.source_name = source_name
    
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
        # TODO: Integrate with logging system
        print(f"[PARSER FAILURE] {self.source_name}: {message}")
    
    def calculate_match_score(self, record: Dict[str, Any], search_params: Dict[str, Any]) -> int:
        """Calculate match confidence score (0-100)
        
        Args:
            record: Extracted record data
            search_params: Original search parameters
        
        Returns:
            Match score 0-100
        """
        score = 0
        
        # Name match (40 points max)
        if 'name' in record and record['name']:
            surname_match = self._fuzzy_match(
                search_params.get('surname', ''),
                record['name']
            )
            given_name_match = self._fuzzy_match(
                search_params.get('given_name', ''),
                record['name']
            )
            score += int((surname_match + given_name_match) / 2 * 40)
        
        # Birth year match (30 points max)
        if 'birth_year' in record and record['birth_year']:
            year_min = search_params.get('year_min')
            year_max = search_params.get('year_max')
            if year_min and year_max:
                birth_year = record['birth_year']
                if year_min <= birth_year <= year_max:
                    score += 30
                elif abs(birth_year - year_min) <= 2 or abs(birth_year - year_max) <= 2:
                    score += 20  # Within 2 years
        
        # Location match (30 points max)
        if 'birth_place' in record and record['birth_place']:
            location_match = self._fuzzy_match(
                search_params.get('location', ''),
                record['birth_place']
            )
            score += int(location_match * 30)
        
        return min(score, 100)
    
    def _fuzzy_match(self, search_term: str, text: str) -> float:
        """Simple fuzzy string matching (0.0 to 1.0)"""
        if not search_term or not text:
            return 0.0
        
        search_term = search_term.lower()
        text = text.lower()
        
        # Exact match
        if search_term in text:
            return 1.0
        
        # Partial match (simple Levenshtein-like)
        # TODO: Use proper fuzzy matching library
        common_chars = sum(1 for c in search_term if c in text)
        return common_chars / len(search_term)

