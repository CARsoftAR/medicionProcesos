import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    '├¡': 'í',
    '├│': 'ó',
    '├í': 'á',
    '├║': 'ú',
    '├®': 'é',
    '├▒': 'ñ',
    '├\xad': 'í', # sometimes shown as this
    '├\xb3': 'ó',
    '├\xa1': 'á',
    '├\xba': 'ú',
    '├\xa9': 'é',
    '├\xb1': 'ñ',
    '┬í': '¡',
    'Verificaci├│n': 'Verificación',
    'Art├¡culo': 'Artículo',
    'Denominaci├│n': 'Denominación',
    'Operaci├│n': 'Operación',
    'N├║mero': 'Número',
    'conexi├│n': 'conexión',
    'importaci├│n': 'importación',
    'desalineaci├│n': 'desalineación',
    'Atenci├│n': 'Atención',
    'autom├íticamente': 'automáticamente',
    'Paginaci├│n': 'Paginación',
    'b├ísica': 'básica',
    'procesar├í': 'procesará',
    '┬íPROCESO': '¡PROCESO',
    'Importaci├│n': 'Importación',
    'alg├║n': 'algún',
    'num├®ricamente': 'numéricamente',
    'VERIFICACIÓ|N': 'VERIFICACIÓN'
}

for bad, good in replacements.items():
    text = text.replace(bad, good)

# Ensure meta charset is present at the very beginning of the block if it's not extending
if '{% extends' not in text[:500] and '<meta charset="UTF-8">' not in text:
    if '<head>' in text:
        text = text.replace('<head>', '<head>\n    <meta charset="UTF-8">')
    else:
        text = '<meta charset="UTF-8">\n' + text

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed broken encoding characters.')
