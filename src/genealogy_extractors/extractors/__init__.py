"""Genealogy record extractors for various online sources."""

from .base import BaseRecordExtractor
from .ancestry import AncestryExtractor
from .anom import ANOMExtractor
from .antenati import AntenatiExtractor
from .billiongraves import BillionGravesExtractor
from .digitalarkivet import DigitalarkivetExtractor
from .familysearch import FamilySearchExtractor
from .filae import FilaeExtractor
from .findagrave import FindAGraveExtractor
from .freebmd import FreeBMDExtractor
from .geneanet import GeneanetExtractor
from .geni import GeniExtractor
from .irishgenealogy import IrishGenealogyExtractor
from .matchid import MatchIDExtractor
from .matricula import MatriculaExtractor
from .myheritage import MyHeritageExtractor
from .scotlandspeople import ScotlandsPeopleExtractor
from .wikitree import WikiTreeExtractor

__all__ = [
    "BaseRecordExtractor",
    "AncestryExtractor",
    "ANOMExtractor",
    "AntenatiExtractor",
    "BillionGravesExtractor",
    "DigitalarkivetExtractor",
    "FamilySearchExtractor",
    "FilaeExtractor",
    "FindAGraveExtractor",
    "FreeBMDExtractor",
    "GeneanetExtractor",
    "GeniExtractor",
    "IrishGenealogyExtractor",
    "MatchIDExtractor",
    "MatriculaExtractor",
    "MyHeritageExtractor",
    "ScotlandsPeopleExtractor",
    "WikiTreeExtractor",
]