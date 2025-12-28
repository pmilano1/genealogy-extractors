from bs4 import BeautifulSoup
import re

with open('tests/fixtures/findagrave_johnson_mary.html', 'r') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
items = soup.find_all('div', class_='memorial-item')

print(f"Found {len(items)} items\n")

item = items[0]
name_elem = item.find('h3') or item.find(class_=re.compile(r'name|title'))
if name_elem:
    print("Name element HTML:")
    print(name_elem.prettify()[:500])
    print(f"\nget_text(strip=True): {repr(name_elem.get_text(strip=True))}")
    print(f"get_text(' ', strip=True): {repr(name_elem.get_text(' ', strip=True))}")
