import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's remove the stray {% if success %}
# We'll just replace `{% if success %}` when it precedes `<!-- SELECTORES DE VINCULACI`
text = re.sub(r'\{%\s*if success\s*%\}\s*<!-- SELECTORES DE VINCULACI.*?-->', r'<!-- SELECTORES DE VINCULACIÓN -->', text, flags=re.DOTALL)

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Removed stray {% if success %}")
