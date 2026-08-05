import re
with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    text = f.read()
ids = re.findall(r'id=[\'\"]([^\'\"]+)[\'\"]', text)
print('IDs found:', set(ids))
