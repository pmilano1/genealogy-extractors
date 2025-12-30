# Staged Findings Review

**Database**: `192.168.20.10:5432/genealogy_local`  
**Table**: `staged_findings`  
**Generated**: 2025-12-30

## Summary

| Metric | Value |
|--------|-------|
| Total pending findings | 13,634 |
| Unique people | 184 |
| With parent data | 3,849 |
| High confidence (≥90) with parents | 2,368 |
| **Unique people with parent data** | **166** |

## By Source

| Source | Count | Avg Score | High Confidence (≥90) |
|--------|-------|-----------|----------------------|
| familysearch | 3,360 | 79.6 | 1,292 |
| myheritage | 3,165 | 82.0 | 904 |
| ancestry | 3,149 | 87.4 | 1,849 |
| geneanet | 1,200 | 97.2 | 1,052 |
| filae | 970 | 91.5 | 633 |
| geni | 907 | 80.7 | 146 |
| findagrave | 396 | 99.9 | 395 |
| freebmd | 356 | 100.0 | 356 |
| antenati | 131 | 92.4 | 97 |

## Quality Tiers

| Confidence | Count | Recommendation |
|------------|-------|----------------|
| Score 100 | ~120 | ✅ Ready to apply |
| Score 95-99 | ~15 | ✅ Apply after quick review |
| Score 90-94 | ~10 | ⚠️ Verify before applying |
| Score 80-89 | ~38 | ❌ Manual review required |

## Known Issues

### 1. Garbage Data (Score 80-85)
Biblical/mythological figures with false matches:
- "Sedequetelebab Kait Kauket" 
- "Ura hijo de Arpaksad"
- "Héber (Eber)"
- "Ermengarde de Tours Reine des Francs"

**Action**: Filter out records with score < 90 or flag for manual review.

### 2. Swapped Father/Mother
Some FamilySearch records have parent names in wrong fields:
- "Arthur Leovide Cardinal" - mother="Jean Baptiste Cardinal" (should be father)
- "Angelo Serena" - father="Giuseppa Salvi" (female name)

**Action**: Add validation to check gender of parent names.

### 3. Common Name Conflicts
Multiple conflicting parent sets for common names:
- "Richard Smith" - 4+ different parent combinations
- "Michael Smith" - 3+ different parent combinations

**Action**: Require higher confidence (≥95) for common surnames.

## Top Candidates for Import (Score 100, Both Parents)

| Person | Born | Father | Mother | Source |
|--------|------|--------|--------|--------|
| Alexandre François de Beauharnais | 1760 | François de Beauharnais | Marie Anne Henriette de Pyvart de Chastullé | geneanet |
| François de Beauharnais, Marquis | 1714 | Claude de Beauharnais | Renée Hardouineau | geneanet |
| Antonino Sinatra | 1780 | Isidoro Sinatra | Antonia Romano | geneanet |
| Ava Lavinia Gardner | 1922 | Jack Gardner | Mary Elizabeth Gardner | geni |
| Nancy Rose Barbato Sinatra | 1917 | Michaelangelo Barbato | Jennie | geneanet |
| Mia Farrow | 1950 | John V Farrow | Maureen O Farrow | familysearch |
| Claire DIDIOT | 1906 | André Didiot | Marie Weber | filae |
| Gaspard DIDIOT | 1746 | Joachim Didiot | Barbe Baltzer | geneanet |
| Jean Jacques BALTZER | 1671 | Josse Baltzer | Julienne Janert | geneanet |
| Marie Anne Henriette Pyvart de Chastullé | 1722 | François Jacques Pyvart de Chastullé | Jeanne Hardouineau | filae |

## Queries

### Get best match per person with parent data:
```sql
WITH best AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY person_id 
    ORDER BY 
      CASE WHEN extracted_record->'raw_data'->>'father' IS NOT NULL THEN 1 ELSE 0 END +
      CASE WHEN extracted_record->'raw_data'->>'mother' IS NOT NULL THEN 1 ELSE 0 END DESC,
      match_score DESC
  ) as rank
  FROM staged_findings WHERE status = 'pending' AND match_score >= 90
)
SELECT person_name, source_name, match_score,
  extracted_record->'raw_data'->>'father' as father,
  extracted_record->'raw_data'->>'mother' as mother
FROM best WHERE rank = 1 
  AND (extracted_record->'raw_data'->>'father' IS NOT NULL 
       OR extracted_record->'raw_data'->>'mother' IS NOT NULL);
```

### Mark as approved:
```sql
UPDATE staged_findings SET status = 'approved', reviewed_at = NOW() 
WHERE id IN (...);
```

## Next Steps

1. **Filter to score ≥95** - reduces to ~80 clean additions
2. **Build approval UI** - review each before submitting to genealogy API
3. **Add gender validation** - detect swapped parent names
4. **Dedupe by person_id** - keep only best match per person

