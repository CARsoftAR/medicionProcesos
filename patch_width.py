import re

with open('mediciones/templates/mediciones/estadisticas_control.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace .ec-left-col width
old_css = '''    .ec-left-col {
        flex: 0 0 250px;
        width: 250px;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        min-height: 0;
        min-width: 0;
    }'''

new_css = '''    .ec-left-col {
        flex: 0 0 270px;
        width: 270px;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        min-height: 0;
        min-width: 0;
    }'''

html = html.replace(old_css, new_css)

with open('mediciones/templates/mediciones/estadisticas_control.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Updated width of .ec-left-col to 270px.')
