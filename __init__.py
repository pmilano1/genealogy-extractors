"""
Genealogy Sources - Modular source checking system
"""

from .base import BaseSource
from .antenati import AntenatiSource
from .geneanet import GeneanetSource
from .wikitree import WikiTreeSource
from .findagrave import FindAGraveSource
from .freebmd import FreeBMDSource

__all__ = [
    'BaseSource',
    'AntenatiSource',
    'GeneanetSource',
    'WikiTreeSource',
    'FindAGraveSource',
    'FreeBMDSource',
]

SOURCES = [
    AntenatiSource(),
    GeneanetSource(),
    WikiTreeSource(),
    FindAGraveSource(),
    FreeBMDSource(),
]

