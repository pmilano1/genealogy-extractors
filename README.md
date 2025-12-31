# Genealogy Extractors

Extract genealogy records from 16+ online sources. Includes both single-search CLI and batch research runner with staging/review workflow.

## Companion to Kindred

This tool is designed to work with **[Kindred](https://github.com/pmilano1/kindred)** - a self-hostable genealogy web application. It uses Kindred's Research Tasks API to:
- Fetch people needing ancestry research
- Search external genealogy sites for records
- Stage findings for human review
- Submit approved findings back to your family tree

> ⚠️ **Use at your own risk.** This tool automates web scraping of genealogy sites, which may violate their terms of service. Always review findings before submitting to your tree.

## Installation

```bash
# Clone and install
git clone https://github.com/pmilano1/genealogy-extractors.git
cd genealogy-extractors
pip install -e .

# Or just run directly
python extract.py --help
python research.py --help
```

## Project Structure

```
genealogy-extractors/
├── extract.py                    # Single-person extraction CLI
├── research.py                   # Batch research runner CLI
├── pyproject.toml                # Package configuration
├── src/genealogy_extractors/     # Library code
│   ├── extractors/               # Source-specific extractors
│   ├── api_client.py             # GraphQL API client
│   ├── cdp_client.py             # Chrome DevTools Protocol client
│   ├── debug_log.py              # Logging utilities
│   └── ...
├── scripts/                      # Utility scripts
└── tests/                        # Test files
```

## Configuration

Configuration is stored in `~/.genealogy-extractors/config.json`.

**Default behavior** (no config needed): Uses SQLite at `~/.genealogy-extractors/genealogy.db`

**For PostgreSQL or API access**, create the config file:

```json
{
  "database": {
    "type": "postgresql",
    "host": "localhost",
    "port": 5432,
    "database": "genealogy",
    "user": "postgres",
    "password": "your_password"
  },
  "api": {
    "endpoint": "https://your-kindred-instance.com/api/graphql",
    "key": "your_api_key"
  },
  "chrome": {
    "debug_port": 9222,
    "debug_host": "127.0.0.1"
  }
}
```

**Chrome with debug port** (required for sites needing login):
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=$HOME/.chrome-debug-profile &
```

**Log into these sites in Chrome** (sessions persist):
- Ancestry.com, MyHeritage.com, FamilySearch.org, Filae.com, Geneanet.org

---

## extract.py - Single Search

Search for a person across one or all sources.

```bash
# Search single source
python extract.py --source findagrave --surname Smith --given-name John --birth-year 1850

# Search all sources
python extract.py --all-sources --surname Smith --given-name John --birth-year 1850

# Verbose output
python extract.py --source matchid --surname Dupont --given-name Marie --birth-year 1920 -v
```

### Options

| Option | Description |
|--------|-------------|
| `--source SOURCE` | Search specific source |
| `--all-sources` | Search all available sources |
| `--surname NAME` | Last name to search |
| `--given-name NAME` | First name to search |
| `--birth-year YEAR` | Birth year (approximate) |
| `--location PLACE` | Birth location hint |
| `--verbose` / `-v` | Show debug output |
| `--test` | Use fixture files instead of live fetch |

---

## research.py - Batch Research

Search all sources for multiple people from your family tree API.

```bash
# Research 50 people
python research.py --limit 50

# Research specific source only
python research.py --source geneanet --limit 10

# Review staged findings
python research.py --review

# Submit approved findings to API
python research.py --submit-approved
```

### Commands

| Command | Description |
|---------|-------------|
| `--limit N` | Process N people |
| `--all` | Process ALL people (no limit) |
| `--source SOURCE` | Single source only |
| `--review` | Interactive review of findings |
| `--summary` | Show staging summary |
| `--submit-approved` | Submit approved to API |
| `--stats` | Show processing statistics |
| `--errors` | Show error summary |
| `--reset` | Clear tracking, re-search all |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--min-score` | 30.0 | Minimum match score |
| `--verbose` / `-v` | off | Debug output |
| `--sequential` | off | Disable parallel |
| `--workers` | 8 | Parallel threads |

### Workflow

1. **Research**: `python research.py --limit 50`
   - Searches sources in parallel per person
   - Skips already-searched combinations
   - Stages findings with score ≥30

2. **Review**: `python research.py --review`
   - `[a]pprove`, `[r]eject`, `[s]kip`, `[q]uit`

3. **Submit**: `python research.py --submit-approved`
   - Creates parent records via API
   - Adds source citations

---

## Supported Sources (16)

| Source | Type | Region | Auth |
|--------|------|--------|------|
| **Find A Grave** | Burials | Global | None |
| **Geneanet** | Trees | Europe | Login |
| **Ancestry** | Records | Global | Login |
| **MyHeritage** | Records | Global | Login |
| **FamilySearch** | Records | Global | Login |
| **Filae** | Civil | France | Login |
| **Geni** | Trees | Global | None |
| **Antenati** | Civil | Italy | None |
| **FreeBMD** | BMD | UK | None |
| **MatchID** | Deaths | France | API Key |
| **ANOM** | Colonial | France | None |
| **Matricula** | Church | Europe | None |
| **Digitalarkivet** | Records | Norway | None |
| **BillionGraves** | Burials | Global | None |
| **IrishGenealogy** | BMD | Ireland | None |
| **ScotlandsPeople** | BMD | Scotland | Login |
| **WikiTree** | Trees | Global | API |

---

## Kindred API Integration

Connects to the Kindred app's GraphQL API to fetch people needing research and submit findings.

```python
from genealogy_extractors.api_client import get_all_people_iterator, submit_research

# Get people needing research from Kindred
for person in get_all_people_iterator():
    print(person['name_full'])

# Submit research finding to Kindred
submit_research(person_id, parent_type, parent_data, source_citation)
```

Default endpoint: `https://family.milanese.life/api/graphql` (configurable via `GENEALOGY_API_KEY`)

---

## Adding New Extractors

1. Create `src/genealogy_extractors/extractors/newsite.py`:
```python
from .base import BaseRecordExtractor

class NewSiteExtractor(BaseRecordExtractor):
    def __init__(self):
        super().__init__("NewSite")

    def extract_records(self, content, search_params):
        # Parse HTML/JSON and return records
        return [{"name": "...", "birth_year": 1850, ...}]
```

2. Add to `extractors/__init__.py`
3. Add source config to `extract.py` SOURCES dict

---

## Data Storage

| Config | Storage | Notes |
|--------|---------|-------|
| No config file | SQLite | `~/.genealogy-extractors/genealogy.db` |
| `database.type: "sqlite"` | SQLite | Uses `database.sqlite_path` |
| `database.type: "postgresql"` | PostgreSQL | Uses host/port/database/user/password |

Tables created automatically: `search_log`, `staged_findings`

---

## License

MIT
