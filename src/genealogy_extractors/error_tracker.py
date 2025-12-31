"""
Error Tracker - Logs and tracks errors for later analysis

Tracks errors by source, type, and frequency to identify patterns
and prioritize fixes.
"""

import json
import os
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional


class ErrorTracker:
    """Thread-safe error tracking with persistence"""
    
    def __init__(self, log_file: str = "error_log.json"):
        self.log_file = log_file
        self.lock = Lock()
        self.errors: List[Dict] = []
        self.error_counts: Dict[str, int] = {}
        self._load_existing()
    
    def _load_existing(self):
        """Load existing error log if present"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
                    self.errors = data.get('errors', [])
                    self.error_counts = data.get('counts', {})
            except Exception:
                pass  # Start fresh if corrupted
    
    def log_error(
        self,
        source: str,
        error_type: str,
        message: str,
        search_params: Optional[Dict] = None,
        stack_trace: Optional[str] = None
    ):
        """Log an error with context"""
        with self.lock:
            error_key = f"{source}:{error_type}"
            
            error_entry = {
                'timestamp': datetime.now().isoformat(),
                'source': source,
                'error_type': error_type,
                'message': message[:500],  # Truncate long messages
                'search_params': search_params,
                'stack_trace': stack_trace[:1000] if stack_trace else None
            }
            
            self.errors.append(error_entry)
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
            
            # Keep only last 1000 errors
            if len(self.errors) > 1000:
                self.errors = self.errors[-1000:]
            
            self._save()
    
    def _save(self):
        """Persist error log to disk"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump({
                    'errors': self.errors,
                    'counts': self.error_counts,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"[ERROR TRACKER] Failed to save: {e}")
    
    def get_summary(self) -> Dict:
        """Get error summary by source and type"""
        with self.lock:
            summary = {
                'total_errors': len(self.errors),
                'by_source': {},
                'by_type': {},
                'top_errors': []
            }
            
            # Group by source
            for error in self.errors:
                source = error['source']
                if source not in summary['by_source']:
                    summary['by_source'][source] = 0
                summary['by_source'][source] += 1
                
                etype = error['error_type']
                if etype not in summary['by_type']:
                    summary['by_type'][etype] = 0
                summary['by_type'][etype] += 1
            
            # Top errors by count
            sorted_counts = sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            summary['top_errors'] = sorted_counts[:10]
            
            return summary
    
    def clear(self):
        """Clear all errors"""
        with self.lock:
            self.errors = []
            self.error_counts = {}
            self._save()


# Global error tracker instance
_error_tracker = ErrorTracker()


def get_error_tracker() -> ErrorTracker:
    """Get the global error tracker instance"""
    return _error_tracker


def log_error(source: str, error_type: str, message: str, **kwargs):
    """Convenience function to log an error"""
    _error_tracker.log_error(source, error_type, message, **kwargs)

