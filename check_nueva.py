import re
with open('mediciones/templates/mediciones/nueva_medicion_op.html', 'r', encoding='utf-8') as f:
    text = f.read()

print("Searching for layout css in nueva_medicion_op.html...")
for match in re.finditer(r'\.layout-wrapper[^{]*\{[^}]*\}', text):
    print(match.group(0))

for match in re.finditer(r'\.sidebar[^{]*\{[^}]*\}', text):
    print(match.group(0))

for match in re.finditer(r'width:[^;]*;', text):
    # just print some widths to see
    pass
