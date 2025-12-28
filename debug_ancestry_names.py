#!/usr/bin/env python3
"""Debug Ancestry name extraction"""

from bs4 import BeautifulSoup

with open('tests/fixtures/ancestry_smith_john.html', 'r') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
cards = soup.find_all('div', class_='global-results-card')

print(f"Found {len(cards)} cards\n")

for i, card in enumerate(cards[:5], 1):
    table = card.find('table', class_='tableHorizontal')
    if table:
        for row in table.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td and th.get_text(strip=True).lower() == 'name':
                print(f"{i}. RAW HTML:")
                print(td.prettify()[:500])
                print(f"\n   RAW TEXT: {repr(td.get_text(strip=True))}")
                print(f"   CLEANED: {repr(td.get_text(' ', strip=True))}")
                print()
                break
