# Genealogy Research Runner

Automated genealogy enrichment system. Searches 9 sources in parallel for people in your family tree, stages findings for review, then submits approved matches to the API.

## Prerequisites

1. **Chrome running with debug port**:
   ```bash
   google-chrome --remote-debugging-port=9222 --user-data-dir=$HOME/.chrome-debug-profile &
   ```

2. **Log into these sites in Chrome** (sessions persist):
   - Ancestry.com
   - MyHeritage.com
   - FamilySearch.org
   - Filae.com (if researching French ancestry)

## Quick Start

```bash
cd ~/workspace/repos/genealogy-extractors

# Run research for 50 people
python research_runner.py --limit 50

# Review staged findings
python research_runner.py --review

# Submit approved findings to API
python research_runner.py --submit-approved
```

## Commands

| Command | Description |
|---------|-------------|
| `--limit N` | Process N people (searches all sources per person) |
| `--all` | Process ALL people in family tree (no limit) |
| `--source SOURCE` | Search single source only |
| `--review` | Interactively review staged findings |
| `--summary` | Show summary of staged findings |
| `--submit-approved` | Submit approved findings to API |
| `--stats` | Show processing statistics |
| `--errors` | Show error tracking summary |
| `--reset` | Clear tracking (re-search everything) |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--min-score` | 30.0 | Minimum match score to stage |
| `--staging-file` | staged_findings.json | Path to staging file |
| `--verbose` / `-v` | off | Show detailed output |
| `--sequential` | off | Disable parallel (one source at a time) |
| `--workers` | 8 | Max parallel threads |

## Workflow

1. **Research**: `python research_runner.py --limit 50`
   - Searches 9 sources in parallel per person
   - Skips already-searched person+source combinations
   - Stages findings scoring ≥30 to `staged_findings.json`

2. **Review**: `python research_runner.py --review`
   - Shows each finding with extracted data
   - `[a]pprove`, `[r]eject`, `[s]kip`, `[q]uit`

3. **Submit**: `python research_runner.py --submit-approved`
   - Sends approved findings to genealogy API
   - Creates parent records with source citations

## Sources (9 total)

| Source | Status | Notes |
|--------|--------|-------|
| Find A Grave | ✅ | Burial records, death dates |
| Geneanet | ✅ | European family trees |
| Ancestry | ✅ | Requires login |
| MyHeritage | ✅ | Requires login |
| FamilySearch | ✅ | Free, requires login |
| Filae | ✅ | French records |
| Geni | ✅ | World family tree |
| Antenati | ✅ | Italian civil records |
| FreeBMD | ✅ | UK birth/marriage/death |
| WikiTree | ⏸️ | Skipped (rate limited) |

## Incremental Processing

The runner tracks which person+source combinations have been searched:

- **First run**: Searches all sources for each person
- **Second run**: Skips already-searched combinations
- **After `--reset`**: Searches everything again

Check progress: `python research_runner.py --stats`

## Files

| File | Purpose |
|------|---------|
| `staged_findings.json` | Pending findings awaiting review |
| `processed_searches.json` | Tracks searched person+source combos |
| `error_log.json` | Error tracking for debugging |
