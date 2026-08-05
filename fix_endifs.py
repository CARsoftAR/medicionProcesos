import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix broken selects by injecting the missing {% endif %}
html = html.replace('{% if not auto_matched.cliente_id %}selected>', '{% if not auto_matched.cliente_id %}selected{% endif %}>')
html = html.replace('{% if c.id == auto_matched.cliente_id %}selected>', '{% if c.id == auto_matched.cliente_id %}selected{% endif %}>')

html = html.replace('{% if not auto_matched.proceso_id %}selected>', '{% if not auto_matched.proceso_id %}selected{% endif %}>')
html = html.replace('{% if p.id == auto_matched.proceso_id %}selected>', '{% if p.id == auto_matched.proceso_id %}selected{% endif %}>')

html = html.replace('{% if not auto_matched.articulo_id %}selected>', '{% if not auto_matched.articulo_id %}selected{% endif %}>')
html = html.replace('{% if a.id == auto_matched.articulo_id %}selected>', '{% if a.id == auto_matched.articulo_id %}selected{% endif %}>')

html = html.replace('{% if not auto_matched.elemento_id %}selected>', '{% if not auto_matched.elemento_id %}selected{% endif %}>')
html = html.replace('{% if e.id == auto_matched.elemento_id %}selected>', '{% if e.id == auto_matched.elemento_id %}selected{% endif %}>')

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed endifs in selects.')
