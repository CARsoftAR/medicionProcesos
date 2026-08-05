import re
with open('mediciones/templates/mediciones/estadisticas_control.html', 'r', encoding='utf-8') as f:
    text = f.read()

print("Searching for layout css in estadisticas_control.html...")
for match in re.finditer(r'\.layout-wrapper[^{]*\{[^}]*\}', text):
    print(match.group(0))

for match in re.finditer(r'\.sidebar[^{]*\{[^}]*\}', text):
    print(match.group(0))
    
for match in re.finditer(r'\.side[^{]*\{[^}]*\}', text):
    print(match.group(0))
