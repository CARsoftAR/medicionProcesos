import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    text = f.read()

print("Table classes found:")
for match in re.finditer(r'<table.*?class="([^"]*)"', text):
    print(match.group(1))

print("Table IDs found:")
for match in re.finditer(r'<table.*?id="([^"]*)"', text):
    print(match.group(1))
