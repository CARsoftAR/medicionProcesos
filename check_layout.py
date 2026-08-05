import re
with open('mediciones/templates/mediciones/ingreso_mediciones.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's search for widths near the top or classes like sidebar
print("Searching for layout css...")
for match in re.finditer(r'\.layout-wrapper[^{]*\{[^}]*\}', text):
    print(match.group(0))

for match in re.finditer(r'\.sidebar-controls[^{]*\{[^}]*\}', text):
    print(match.group(0))

for match in re.finditer(r'\.side[^{]*\{[^}]*\}', text):
    print(match.group(0))
