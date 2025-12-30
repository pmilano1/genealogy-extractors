"""
Genealogy Record Extractors
Source-specific parsers for extracting structured data from search results
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

__all__ = [
    'BaseRecordExtractor',
    'FindAGraveExtractor',
    'GeneanetExtractor',
    'AntenatiExtractor',
    'FilaeExtractor',
    'FreeBMDExtractor',
    'WikiTreeExtractor',
    'FamilySearchExtractor',
    'MyHeritageExtractor',
    'AncestryExtractor',
    'GeniExtractor',
    'BillionGravesExtractor',
    'DigitalarkivetExtractor',
    'IrishGenealogyExtractor',
    'MatriculaExtractor',
    'ScotlandsPeopleExtractor',
]
