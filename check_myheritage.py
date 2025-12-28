from bs4 import BeautifulSoup

with open('tests/fixtures/myheritage_smith_john.html', 'r') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Find all divs with class containing 'item' or 'card' or 'person'
for tag in ['div', 'li', 'tr']:
    items = soup.find_all(tag, class_=lambda x: x and any(word in x.lower() for word in ['item', 'card', 'person', 'row']))
    if items:
        print(f"\nFound {len(items)} {tag} elements")
        print(f"First element classes: {items[0].get('class')}")
        print(f"First 300 chars:\n{items[0].get_text(' ', strip=True)[:300]}")
        break
