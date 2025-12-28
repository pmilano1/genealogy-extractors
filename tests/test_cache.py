"""
Test cache module
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.cache import PersistentSearchCache


def test_cache_basic():
    """Test basic cache operations"""
    # Create temporary cache directory
    cache_dir = tempfile.mkdtemp()
    
    try:
        cache = PersistentSearchCache(cache_dir)
        
        # Test cache miss
        result = cache.get("Find A Grave", "Smith", "John", "London", 1850, 1900)
        assert result is None, "Cache should be empty initially"
        
        # Test cache set
        test_result = {
            'found': True,
            'message': 'FOUND (10 results)',
            'url': 'https://example.com/search'
        }
        cache.set("Find A Grave", "Smith", "John", "London", 1850, 1900, test_result)
        
        # Test cache hit
        cached_result = cache.get("Find A Grave", "Smith", "John", "London", 1850, 1900)
        assert cached_result is not None, "Cache should return result"
        assert cached_result['found'] == True, "Cached result should match"
        assert cached_result['message'] == 'FOUND (10 results)', "Cached message should match"
        
        # Test cache stats
        stats = cache.stats()
        assert stats['total'] == 1, "Should have 1 cache entry"
        assert stats['valid'] == 1, "Should have 1 valid entry"
        assert stats['expired'] == 0, "Should have 0 expired entries"
        
        print("✓ All cache tests passed")
    
    finally:
        # Cleanup
        shutil.rmtree(cache_dir)


def test_cache_key_uniqueness():
    """Test that different search parameters generate different cache keys"""
    cache_dir = tempfile.mkdtemp()
    
    try:
        cache = PersistentSearchCache(cache_dir)
        
        # Set two different searches
        cache.set("Find A Grave", "Smith", "John", "London", 1850, 1900, {'result': 'A'})
        cache.set("Find A Grave", "Smith", "Jane", "London", 1850, 1900, {'result': 'B'})
        
        # Verify they're stored separately
        result_a = cache.get("Find A Grave", "Smith", "John", "London", 1850, 1900)
        result_b = cache.get("Find A Grave", "Smith", "Jane", "London", 1850, 1900)
        
        assert result_a['result'] == 'A', "Should get correct result for John"
        assert result_b['result'] == 'B', "Should get correct result for Jane"
        
        stats = cache.stats()
        assert stats['total'] == 2, "Should have 2 cache entries"
        
        print("✓ Cache key uniqueness test passed")
    
    finally:
        shutil.rmtree(cache_dir)


if __name__ == "__main__":
    print("Running cache tests...")
    test_cache_basic()
    test_cache_key_uniqueness()
    print("\n✅ All tests passed!")

