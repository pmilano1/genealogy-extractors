# MyHeritage Results Fixture Needed

The current fixture `tests/fixtures/myheritage_smith_john.html` contains the search FORM page, not actual search RESULTS.

To fix this, we need actual MyHeritage search results HTML.

## How to Get It:

1. Log into MyHeritage (requires subscription)
2. Search for "John Smith" born around 1875 in London
3. Save the results page HTML
4. Replace the current fixture

## Alternative:

Since MyHeritage requires subscription and has bot detection, we could:
- Mark it as MANUAL_ONLY in the source config
- Skip automated testing for MyHeritage
- Document that it requires manual browser access

For now, I'll disable the MyHeritage test until we have proper results HTML.
