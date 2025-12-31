"""
MatchID Extractor - French Death Records API (1970-present)

MatchID provides free access to ~28 million French death records from INSEE.
API documentation: https://matchid.io/link-api

Access method: API (JSON)
Rate limit: 1 request/second without auth, unlimited with token

Data captured:
- Full name (surname + given names)
- Sex
- Birth: date, city, department, country, INSEE code, postal codes, GPS coordinates
- Death: date, city, department, country, age, certificate ID, GPS coordinates
- Source file (year) and line number
- Match scores
"""

import re
import requests
from typing import Any, Dict, List, Optional
from .base_extractor import BaseRecordExtractor


class MatchIDExtractor(BaseRecordExtractor):
    """Extractor for MatchID French death records API."""

    BASE_URL = "https://deces.matchid.io/deces/api/v1"
    SOURCE_NAME = "MatchID"
    # Default token - can be overridden via MATCHID_API_TOKEN env var or constructor
    DEFAULT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoicGV0ZXJtQG1pbGFuZXNlLmxpZmUiLCJwYXNzd29yZCI6IjEzNDExOCIsInNjb3BlcyI6WyJ1c2VyIl0sImlhdCI6MTc2NzE5NTY4NCwiZXhwIjoxNzY5Nzg3Njg0LCJqdGkiOiIxNzY3MTk1Njg0In0.yZ1dxqHHlWKciu2CvP6Tru1eVT3VrLs3Bs63-e0-T-k"

    def __init__(self, api_token: str | None = None):
        """Initialize with optional API token for unlimited requests.

        Token priority: 1) constructor arg, 2) MATCHID_API_TOKEN env var, 3) default token
        """
        import os
        super().__init__("MatchID")
        self.api_token = api_token or os.environ.get("MATCHID_API_TOKEN") or self.DEFAULT_TOKEN

    def build_search_url(
        self,
        surname: str,
        given_name: str | None = None,
        birth_year: int | None = None,
        birth_place: str | None = None,
        death_year: int | None = None,
        size: int = 20,
    ) -> str:
        """Build search URL for MatchID API.

        Note: Date filters use format YYYY-MM-DD to YYYY-MM-DD or year ranges.
        The API is quite flexible with date formats.
        """
        from urllib.parse import quote

        # Build query string - include name parts in free text query
        query_parts = [surname]
        if given_name:
            query_parts.append(given_name)
        if birth_place:
            query_parts.append(birth_place)

        # For birth year, add to query as text (more flexible than birthDate filter)
        if birth_year:
            query_parts.append(str(birth_year))

        params = {"q": " ".join(query_parts), "size": size}

        # Build URL with proper encoding
        param_str = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{self.BASE_URL}/search?{param_str}"

    def search(
        self,
        surname: str,
        given_name: str | None = None,
        birth_year: int | None = None,
        birth_place: str | None = None,
        death_year: int | None = None,
        size: int = 20,
    ) -> list[dict[str, Any]]:
        """Search MatchID API and return parsed records."""
        url = self.build_search_url(
            surname, given_name, birth_year, birth_place, death_year, size
        )

        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        return self.extract_records(data, {"surname": surname, "given_name": given_name})

    def extract_records(
        self, content: dict | str, search_params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract records from MatchID API response."""
        # Handle both dict (from API) and string (from file)
        if isinstance(content, str):
            import json
            data = json.loads(content)
        else:
            data = content

        records = []
        persons = data.get("response", {}).get("persons", [])

        for person in persons:
            record = self._parse_person(person)
            if record:
                records.append(record)

        return records

    def _parse_person(self, person: dict) -> Dict[str, Any] | None:
        """Parse a single person record from MatchID response.

        Captures ALL available fields from the API response.
        """
        try:
            name_data = person.get("name", {})
            birth_data = person.get("birth", {})
            death_data = person.get("death", {})

            # Build full name
            first_names = name_data.get("first", [])
            last_name = name_data.get("last", "")
            full_name = f"{last_name}, {' '.join(first_names)}" if first_names else last_name

            # Parse dates (format: YYYYMMDD)
            birth_date = self._parse_date(birth_data.get("date"))
            death_date = self._parse_date(death_data.get("date"))

            # Extract locations with ALL fields
            birth_loc = birth_data.get("location", {})
            death_loc = death_data.get("location", {})

            # Helper to extract city (can be string or list)
            def get_city(loc: dict) -> str | None:
                city = loc.get("city")
                if isinstance(city, list):
                    return city[0] if city else None
                return city

            # Store all city variants
            def get_city_variants(loc: dict) -> List[str] | None:
                city = loc.get("city")
                if isinstance(city, list):
                    return city
                return [city] if city else None

            # Extract birth year safely
            birth_year = None
            if birth_data.get("date") and len(birth_data.get("date", "")) >= 4:
                birth_year = int(birth_data.get("date")[:4])

            # Extract death year safely
            death_year = None
            if death_data.get("date") and len(death_data.get("date", "")) >= 4:
                death_year = int(death_data.get("date")[:4])

            record = {
                "source": self.SOURCE_NAME,
                "id": person.get("id"),
                "name": full_name,
                "given_names": first_names,
                "surname": last_name,
                "sex": person.get("sex"),
                # Birth data
                "birth_date": birth_date,
                "birth_year": birth_year,
                "birth_city": get_city(birth_loc),
                "birth_city_variants": get_city_variants(birth_loc),
                "birth_place": get_city(birth_loc),  # Alias for compatibility
                "birth_department": birth_loc.get("departmentCode"),
                "birth_country": birth_loc.get("country"),
                "birth_country_code": birth_loc.get("countryCode"),
                "birth_insee_code": birth_loc.get("code"),
                "birth_postal_codes": birth_loc.get("codePostal"),
                "birth_latitude": birth_loc.get("latitude"),
                "birth_longitude": birth_loc.get("longitude"),
                # Death data
                "death_date": death_date,
                "death_year": death_year,
                "death_city": get_city(death_loc),
                "death_city_variants": get_city_variants(death_loc),
                "death_place": get_city(death_loc),  # Alias for compatibility
                "death_department": death_loc.get("departmentCode"),
                "death_country": death_loc.get("country"),
                "death_country_code": death_loc.get("countryCode"),
                "death_insee_code": death_loc.get("code"),
                "death_postal_codes": death_loc.get("codePostal"),
                "death_latitude": death_loc.get("latitude"),
                "death_longitude": death_loc.get("longitude"),
                "death_age": death_data.get("age"),
                "death_certificate_id": death_data.get("certificateId"),
                # Match scores
                "match_score": person.get("score"),
                "es_score": person.get("scores", {}).get("es"),
                # Source metadata
                "source_file": person.get("source"),
                "source_line": person.get("sourceLine"),
                # URL
                "url": f"https://deces.matchid.io/id/{person.get('id')}",
            }

            # Store raw data for any additional fields
            record["raw_data"] = {
                "scores": person.get("scores"),
                "source": person.get("source"),
                "sourceLine": person.get("sourceLine"),
            }

            return record
        except Exception as e:
            self.warn(f"Failed to parse person: {e}")
            return None

    def _parse_date(self, date_str: str | None) -> str | None:
        """Parse YYYYMMDD date to readable format."""
        if not date_str or len(date_str) < 8:
            return None
        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{day}/{month}/{year}"
        except Exception:
            return date_str

