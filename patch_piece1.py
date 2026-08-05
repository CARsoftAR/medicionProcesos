import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Remove the alert
html = html.replace('alert("Datos cargados correctamente en consola. Ver F12");', '')

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)

with open('mediciones/views.py', 'r', encoding='utf-8') as f:
    views_code = f.read()

# In views.py:
# `pieza_num = piezas_cols[idx]`
# Replace with `pieza_num = int(re.sub(r'[^0-9]', '', str(piezas_cols[idx])))` or similar to prevent crashes
# Wait, if `piezas_cols[idx]` is '1', it should be 1. If it's '26_1', it should be 26. But wait, if they are both 26, it overwrites.
# Let's just do `pieza_num_str = str(piezas_cols[idx]).split('_')[0]; pieza_num = int(re.sub(r'\D', '', pieza_num_str)) if re.sub(r'\D', '', pieza_num_str) else idx + 1`

old_pieza_num = "pieza_num = piezas_cols[idx]"
new_pieza_num = '''pieza_num_raw = str(piezas_cols[idx])
                    try:
                        pieza_num = int(re.sub(r'\\D', '', pieza_num_raw.split('_')[0]))
                    except:
                        pieza_num = idx + 1
                    
                    if pieza_num == 0: pieza_num = 1 # Fallback just in case'''

views_code = views_code.replace(old_pieza_num, new_pieza_num)

with open('mediciones/views.py', 'w', encoding='utf-8') as f:
    f.write(views_code)

print('Patched frontend alert and backend pieza_num parsing.')
