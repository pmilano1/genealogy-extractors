"""
French location resolver for Filae searches.
Uses static GeoNames data to build proper Filae search URLs with location filtering.
"""

import json
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class FrenchLocation:
    """A French location with GeoNames data for Filae searches."""
    gid: int           # GeoNames ID
    name: str          # Location name
    lat: float         # Latitude
    lon: float         # Longitude
    fc: str            # Feature code (ADM1=region, ADM2=dept, PPLC/PPLA=city)
    type: str          # 'region', 'department', or 'city'
    ri: Optional[int]  # Region ID
    di: Optional[int]  # Department ID
    region: str        # Region name
    department: str    # Department name
    population: int    # Population


class FrenchLocationResolver:
    """Resolves French location names to GeoNames data for Filae searches."""

    # Historical region aliases (pre-2016 regions → current regions)
    REGION_ALIASES = {
        'alsace': 'Grand Est',
        'lorraine': 'Grand Est',
        'champagne-ardenne': 'Grand Est',
        'champagne': 'Grand Est',
        'picardie': 'Hauts-de-France',
        'picardy': 'Hauts-de-France',
        'nord-pas-de-calais': 'Hauts-de-France',
        'aquitaine': 'Nouvelle-Aquitaine',
        'limousin': 'Nouvelle-Aquitaine',
        'poitou-charentes': 'Nouvelle-Aquitaine',
        'languedoc-roussillon': 'Occitanie',
        'midi-pyrénées': 'Occitanie',
        'midi-pyrenees': 'Occitanie',
        'auvergne': 'Auvergne-Rhône-Alpes',
        'rhône-alpes': 'Auvergne-Rhône-Alpes',
        'rhone-alpes': 'Auvergne-Rhône-Alpes',
        'bourgogne': 'Bourgogne-Franche-Comté',
        'burgundy': 'Bourgogne-Franche-Comté',
        'franche-comté': 'Bourgogne-Franche-Comté',
        'franche-comte': 'Bourgogne-Franche-Comté',
        'basse-normandie': 'Normandie',
        'haute-normandie': 'Normandie',
        'centre': 'Centre-Val de Loire',
    }

    def __init__(self):
        self._locations: list[FrenchLocation] = []
        self._load_locations()
    
    def _load_locations(self):
        """Load locations from the JSON data file."""
        data_path = Path(__file__).parent.parent.parent / 'data' / 'french_locations.json'
        if not data_path.exists():
            # Try alternative path
            data_path = Path(__file__).parent.parent.parent.parent / 'data' / 'french_locations.json'
        
        if data_path.exists():
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._locations = [FrenchLocation(**loc) for loc in data]
    
    def _normalize(self, text: str) -> str:
        """Normalize text for fuzzy matching - remove accents, hyphens, articles."""
        import unicodedata
        # Remove accents
        normalized = unicodedata.normalize('NFD', text)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        # Lowercase and strip
        normalized = normalized.lower().strip()
        # Remove common articles and prefixes
        for article in ['le ', 'la ', 'les ', "l'", 'de ', 'du ', 'des ', "d'"]:
            if normalized.startswith(article):
                normalized = normalized[len(article):]
        # Replace hyphens and multiple spaces
        normalized = normalized.replace('-', ' ').replace('  ', ' ')
        return normalized

    def find(self, query: str, type_filter: Optional[str] = None) -> Optional[FrenchLocation]:
        """
        Find a location by name with fuzzy matching.

        Matching priority:
        1. Historical region alias lookup
        2. Exact match (case-insensitive)
        3. Normalized match (no accents, articles)
        4. Starts-with match
        5. Contains match

        Args:
            query: Location name to search for
            type_filter: Optional filter for 'region', 'department', or 'city'

        Returns:
            Best matching FrenchLocation or None
        """
        query_lower = query.lower().strip()
        query_normalized = self._normalize(query)

        # Check historical region aliases first (e.g., 'Alsace' → 'Grand Est')
        if query_lower in self.REGION_ALIASES:
            aliased_name = self.REGION_ALIASES[query_lower]
            for loc in self._locations:
                if loc.name == aliased_name:
                    return loc

        # Exact match (case-insensitive)
        for loc in self._locations:
            if type_filter and loc.type != type_filter:
                continue
            if loc.name.lower() == query_lower:
                return loc

        # Normalized match (handles accents, articles, hyphens)
        for loc in self._locations:
            if type_filter and loc.type != type_filter:
                continue
            if self._normalize(loc.name) == query_normalized:
                return loc

        # Partial match (starts with, normalized)
        for loc in self._locations:
            if type_filter and loc.type != type_filter:
                continue
            if self._normalize(loc.name).startswith(query_normalized):
                return loc

        # Contains match (normalized)
        for loc in self._locations:
            if type_filter and loc.type != type_filter:
                continue
            if query_normalized in self._normalize(loc.name):
                return loc

        return None
    
    def find_by_department(self, dept_name: str) -> Optional[FrenchLocation]:
        """Find a department by name."""
        return self.find(dept_name, type_filter='department')
    
    def find_by_region(self, region_name: str) -> Optional[FrenchLocation]:
        """Find a region by name."""
        return self.find(region_name, type_filter='region')
    
    def find_by_city(self, city_name: str) -> Optional[FrenchLocation]:
        """Find a city by name."""
        return self.find(city_name, type_filter='city')
    
    def build_filae_url(
        self,
        surname: str,
        given_name: str = '',
        birth_year: Optional[int] = None,
        birth_year_end: Optional[int] = None,
        location: Optional[str] = None,
        radius_km: int = 20
    ) -> str:
        """
        Build a Filae search URL with optional location filtering.
        
        Args:
            surname: Last name (required)
            given_name: First name (optional)
            birth_year: Start year for birth range
            birth_year_end: End year for birth range
            location: Location name to filter by (city, department, or region)
            radius_km: Search radius in km (only for cities, ignored for regions/depts)
        
        Returns:
            Complete Filae search URL
        """
        base = "https://www.filae.com/search"
        params = [f"ln={surname}"]
        
        if given_name:
            params.append(f"fn={given_name}")
        if birth_year:
            params.append(f"sy={birth_year}")
        if birth_year_end:
            params.append(f"ey={birth_year_end}")
        
        # Add location parameters if specified
        if location:
            loc = self.find(location)
            if loc:
                params.append(f"gid={loc.gid}")
                params.append(f"lat={loc.lat}")
                params.append(f"lon={loc.lon}")
                params.append(f"fc={loc.fc}")
                if loc.ri:
                    params.append(f"ri={loc.ri}")
                if loc.di:
                    params.append(f"di={loc.di}")
                # pf=2 means 20km radius, pf=0 for no radius (regions/depts)
                if loc.type == 'city':
                    params.append("pf=2")  # 20km radius for cities
                else:
                    params.append("pf=0")  # No radius for regions/departments
        
        return f"{base}?{'&'.join(params)}"


# Module-level instance for convenience
_resolver: Optional[FrenchLocationResolver] = None


def get_resolver() -> FrenchLocationResolver:
    """Get or create the singleton location resolver."""
    global _resolver
    if _resolver is None:
        _resolver = FrenchLocationResolver()
    return _resolver


def build_filae_url(
    surname: str,
    given_name: str = '',
    birth_year: Optional[int] = None,
    birth_year_end: Optional[int] = None,
    location: Optional[str] = None
) -> str:
    """Convenience function to build Filae URLs."""
    return get_resolver().build_filae_url(
        surname=surname,
        given_name=given_name,
        birth_year=birth_year,
        birth_year_end=birth_year_end,
        location=location
    )

