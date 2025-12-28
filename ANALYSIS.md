# Genealogy Extractors - HTML Analysis & Next Steps

## Analysis Date: 2025-12-28

## Sources Analyzed

### 1. Find A Grave ✅ WORKING
**Status**: Extractor works, HTML captured successfully

**Current Fields Extracted**:
- name
- birth_year, death_year  
- birth_place, death_place (combined from location)
- url

**Available But NOT Extracted**:
- `cemetery_name` - Available in `<button title="...">` 
- `photo_url` - Available in `<img src="...">`
- `full_dates` - Exact birth/death dates (e.g., "15 Aug 1871 – 25 Oct 1899")

**HTML Structure**:
```html
<div class="memorial-item">
  <a href="/memorial/271012903/john-smith">
    <img src="https://images.findagrave.com/photoThumbnails/..."/>
    <i class="text-break">John Smith</i>
    <b class="birthDeathDates">15 Aug 1871 – 25 Oct 1899</b>
  </a>
  <button title="Cedar Grove Cemetery">...</button>
  <p class="addr-cemet">Dorchester, Suffolk County, Massachusetts</p>
</div>
```

**Recommendation**: Add cemetery_name, photo_url, and parse full_dates

---

### 2. Geneanet ✅ FIXED
**Status**: URL fixed, now returns results

**Correct URL**: `https://en.geneanet.org/fonds/individus/?nom={surname}&prenom={given_name}&type_periode=birth_between&from={birth_year}&to={birth_year_end}&go=1&size=20`

**Current Fields Extracted**:
- name
- birth_year, death_year
- birth_place, death_place

**Available But NOT Extracted**:
- `spouse_name` - e.g., "SAX Franciska Frances"
- `marriage_year` - e.g., "(1895)"
- `family_tree_owner` - e.g., "Family tree of tedbubert"
- `url` - Link to full record

**Recommendation**: Add spouse, marriage_year, family_tree_owner, url fields

---

### 3. Ancestry ✅ WORKING  
**Status**: Extractor works, HTML captured successfully

**Current Fields Extracted**:
- name
- birth_year, death_year
- birth_place, death_place
- url

**HTML Structure**: JavaScript-rendered, uses `<div class="memorial-item">` (similar to Find A Grave)

**Recommendation**: Analyze HTML for additional fields (spouse, parents, children, collection)

---

### 4. FamilySearch ❌ NO RESULTS
**Status**: HTML captured but 0 results extracted

**Issue**: JavaScript-rendered page, HTML is minimal (7.9K)

**Recommendation**: Needs CDP browser with wait for results to load

---

### 5. Antenati ❌ NO RESULTS
**Status**: HTML captured but 0 results extracted (84K HTML)

**Issue**: Likely JavaScript-rendered or wrong selector

**Recommendation**: Analyze HTML structure to find correct selectors

---

### 6. WikiTree ❌ NOT IMPLEMENTED
**Status**: Requires API implementation

**Recommendation**: Implement WikiTree API or skip

---

## Summary

**Working Sources**: Find A Grave (20 results), Geneanet (FIXED), Ancestry (20 results)
**Broken Sources**: FamilySearch (0 results - JS rendering), Antenati (0 results - wrong selectors)
**Not Implemented**: WikiTree (needs API)

## Next Steps (Priority Order)

1. ✅ **Fix Geneanet URL** - DONE
2. **Enhance Find A Grave** - Add cemetery_name, photo_url, full_dates
3. **Enhance Geneanet** - Add spouse, marriage_year, family_tree_owner, url
4. **Enhance Ancestry** - Extract additional relationship data (spouse, parents, children, collection)
5. **Fix FamilySearch** - Needs CDP browser wait for JS rendering OR different URL
6. **Fix Antenati** - Analyze HTML and fix selectors
7. **MyHeritage** - Already enhanced with full relationship data (DONE)

---

## Files to Update

- `extract.py` - Fix Geneanet URL template
- `extraction/findagrave_extractor.py` - Add cemetery, photo, full dates
- `extraction/familysearch_extractor.py` - Fix selectors or add wait
- `extraction/antenati_extractor.py` - Fix selectors
- `extraction/ancestry_extractor.py` - Add relationship fields

