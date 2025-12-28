# Testing Flags Documentation

## Overview

The `test_e2e_single.py` script now supports command-line flags to control caching and HTML saving behavior.

## Usage

```bash
# Default: cache enabled, no HTML saving
python test_e2e_single.py

# Disable cache (force fresh searches)
python test_e2e_single.py --no-cache

# Save HTML to fixtures directory
python test_e2e_single.py --save-html

# Combine flags
python test_e2e_single.py --no-cache --save-html

# Custom person search
python test_e2e_single.py --surname Weber --given-name Marie --location France --year-min 1880 --year-max 1920
```

## Flags

### `--no-cache`
- **Purpose**: Disable cache and force fresh searches
- **Default**: Cache is ENABLED
- **Use when**: You want to test actual CDP navigation without using cached results
- **Effect**: Uses `CDPOrchestrator` instead of `EnhancedCDPOrchestrator`

### `--save-html`
- **Purpose**: Save HTML content to `tests/fixtures/` directory
- **Default**: HTML is NOT saved
- **Use when**: You want to capture HTML for offline testing or debugging
- **Effect**: Creates files like `findagrave_smith_john.html` in `tests/fixtures/`

### Person Override Flags
- `--surname`: Override test surname (default: Smith)
- `--given-name`: Override test given name (default: John)
- `--location`: Override test location (default: London)
- `--year-min`: Override min year (default: 1850)
- `--year-max`: Override max year (default: 1900)

## How It Works

### Cache Behavior

**With cache (default)**:
- Uses `EnhancedCDPOrchestrator`
- Searches are cached in `.cache/` directory
- Subsequent runs with same parameters use cached results
- Faster for repeated testing

**Without cache (`--no-cache`)**:
- Uses base `CDPOrchestrator`
- Every search navigates to the actual website
- Slower but tests real CDP navigation
- Use for verifying current website behavior

### HTML Saving

**Without `--save-html` (default)**:
- HTML content is used inline for result checking
- Not saved to disk
- Cleaner workspace

**With `--save-html`**:
- HTML content is saved to `tests/fixtures/{source}_{surname}_{given_name}.html`
- Useful for:
  - Offline testing
  - Debugging extractors
  - Comparing HTML changes over time
  - Creating test fixtures

## Examples

### Test with fresh searches and save HTML
```bash
python test_e2e_single.py --no-cache --save-html
```

### Test a specific person with cache
```bash
python test_e2e_single.py --surname Weber --given-name Marie --location "Bas-Rhin, France"
```

### Force fresh searches for a specific person
```bash
python test_e2e_single.py --no-cache --surname Weber --given-name Marie
```

## Output

The script shows the flag status at the start:

```
======================================================================
END-TO-END TEST - ONE SOURCE AT A TIME
======================================================================
Test person: John Smith
Location: London
Years: 1850-1900
Cache: ENABLED
Save HTML: NO
======================================================================
```

When HTML is saved, you'll see:
```
💾 Saved HTML: findagrave_smith_john.html (45.2 KB)
```

## File Locations

- **Cache**: `.cache/` directory (SQLite database)
- **HTML Fixtures**: `tests/fixtures/` directory
- **Logs**: `.logs/` directory

## Best Practices

1. **Development**: Use `--save-html` to capture HTML for extractor development
2. **Testing**: Use `--no-cache` to verify current website behavior
3. **Debugging**: Combine `--no-cache --save-html` to capture fresh HTML
4. **CI/CD**: Use default (cache enabled) for faster test runs
5. **Regression Testing**: Save HTML fixtures and test extractors offline

