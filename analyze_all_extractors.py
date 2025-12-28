#!/usr/bin/env python3
"""Analyze what data is actually available in each fixture"""

from bs4 import BeautifulSoup
import json

fixtures = {
    'Find A Grave': 'tests/fixtures/findagrave_johnson_mary.html',
    'Ancestry': 'tests/fixtures/ancestry_smith_john.html',
    'MyHeritage': 'tests/fixtures/myheritage_smith_john.html',
    'WikiTree': 'tests/fixtures/wikitree_smith_john_api.json',
}

for source, path in fixtures.items():
    print(f"\n{'='*80}")
    print(f"{source}")
    print('='*80)
    
    if path.endswith('.json'):
        with open(path, 'r') as f:
            data = json.load(f)
        print(json.dumps(data[0] if isinstance(data, list) else data, indent=2)[:1000])
    else:
        with open(path, 'r') as f:
            html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        
        if source == 'Find A Grave':
            item = soup.find('div', class_='memorial-item')
            if item:
                print("Full text of first item:")
                print(item.get_text('\n', strip=True)[:800])
        
        elif source == 'Ancestry':
            card = soup.find('div', class_='global-results-card')
            if card:
                table = card.find('table', class_='tableHorizontal')
                if table:
                    print("Table data:")
                    for row in table.find_all('tr')[:5]:
                        th = row.find('th')
                        td = row.find('td')
                        if th and td:
                            print(f"  {th.get_text(strip=True)}: {td.get_text(' ', strip=True)[:100]}")
        
        elif source == 'MyHeritage':
            items = soup.find_all('div', class_=lambda x: x and 'result' in x.lower())[:1]
            if items:
                print("Full text of first result:")
                print(items[0].get_text('\n', strip=True)[:800])

