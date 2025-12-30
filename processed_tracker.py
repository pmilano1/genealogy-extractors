"""
Processed Tracker - Tracks which person+source combinations have been searched

Prevents redundant searches across multiple runs.
"""

import json
import os
from datetime import datetime
from threading import Lock
from typing import Set, Dict, Optional


class ProcessedTracker:
    """Thread-safe tracking of processed person+source combinations"""
    
    def __init__(self, tracker_file: str = "processed_searches.json"):
        self.tracker_file = tracker_file
        self.lock = Lock()
        self.processed: Dict[str, Set[str]] = {}  # person_id -> set of sources
        self.stats: Dict[str, int] = {}  # source -> count
        self._load()
    
    def _load(self):
        """Load existing tracker data"""
        if os.path.exists(self.tracker_file):
            try:
                with open(self.tracker_file, 'r') as f:
                    data = json.load(f)
                    # Convert lists back to sets
                    self.processed = {
                        pid: set(sources) 
                        for pid, sources in data.get('processed', {}).items()
                    }
                    self.stats = data.get('stats', {})
            except Exception:
                self.processed = {}
                self.stats = {}
    
    def _save(self):
        """Persist tracker to disk"""
        try:
            with open(self.tracker_file, 'w') as f:
                json.dump({
                    'processed': {
                        pid: list(sources) 
                        for pid, sources in self.processed.items()
                    },
                    'stats': self.stats,
                    'last_updated': datetime.now().isoformat()
                }, f)
        except Exception as e:
            print(f"[TRACKER] Failed to save: {e}")
    
    def is_processed(self, person_id: str, source: str) -> bool:
        """Check if person+source combo has been searched"""
        with self.lock:
            return source in self.processed.get(person_id, set())
    
    def mark_processed(self, person_id: str, source: str):
        """Mark person+source as processed"""
        with self.lock:
            if person_id not in self.processed:
                self.processed[person_id] = set()
            self.processed[person_id].add(source)
            
            # Update stats
            self.stats[source] = self.stats.get(source, 0) + 1
            
            self._save()
    
    def get_unprocessed_sources(self, person_id: str, all_sources: list) -> list:
        """Get list of sources not yet searched for this person"""
        with self.lock:
            processed = self.processed.get(person_id, set())
            return [s for s in all_sources if s not in processed]
    
    def get_stats(self) -> Dict:
        """Get processing statistics"""
        with self.lock:
            total_people = len(self.processed)
            total_searches = sum(len(sources) for sources in self.processed.values())
            return {
                'total_people': total_people,
                'total_searches': total_searches,
                'by_source': dict(self.stats)
            }
    
    def clear(self):
        """Clear all tracking data"""
        with self.lock:
            self.processed = {}
            self.stats = {}
            self._save()


# Global tracker instance
_tracker = ProcessedTracker()


def get_tracker() -> ProcessedTracker:
    """Get the global processed tracker instance"""
    return _tracker

