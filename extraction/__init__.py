"""
Genealogy Record Extractors
Source-specific parsers for extracting structured data from search results

17 Sources:
- API-based: MatchID (French deaths), WikiTree (disabled)
- CDP Browser: Find A Grave, Geneanet, Antenati, Filae, FreeBMD, BillionGraves,
               FamilySearch, MyHeritage, Ancestry, Geni, ScotlandsPeople,
               IrishGenealogy, Matricula, Digitalarkivet, ANOM
"""

from .base_extractor import BaseRecordExtractor
from .find_a_grave_extractor import FindAGraveExtractor
from .geneanet_extractor import GeneanetExtractor
from .antenati_extractor import AntenatiExtractor
from .filae_extractor import FilaeExtractor
from .freebmd_extractor import FreeBMDExtractor
from .wikitree_extractor import WikiTreeExtractor
from .familysearch_extractor import FamilySearchExtractor
from .myheritage_extractor import MyHeritageExtractor
from .ancestry_extractor import AncestryExtractor
from .geni_extractor import GeniExtractor
from .billiongraves_extractor import BillionGravesExtractor
from .digitalarkivet_extractor import DigitalarkivetExtractor
from .irishgenealogy_extractor import IrishGenealogyExtractor
from .matricula_extractor import MatriculaExtractor
from .scotlandspeople_extractor import ScotlandsPeopleExtractor
from .matchid_extractor import MatchIDExtractor
from .anom_extractor import ANOMExtractor

__all__ = [
    'BaseRecordExtractor',
    # Cemetery/Grave Records
    'FindAGraveExtractor',
    'BillionGravesExtractor',
    # European Genealogy
    'GeneanetExtractor',
    'AntenatiExtractor',
    'FilaeExtractor',
    'MatchIDExtractor',
    # UK/Ireland
    'FreeBMDExtractor',
    'ScotlandsPeopleExtractor',
    'IrishGenealogyExtractor',
    # German/Austrian Church Records
    'MatriculaExtractor',
    # Scandinavian
    'DigitalarkivetExtractor',
    # Commercial Sites
    'FamilySearchExtractor',
    'MyHeritageExtractor',
    'AncestryExtractor',
    'GeniExtractor',
    'WikiTreeExtractor',
    # French Colonial
    'ANOMExtractor',
]
