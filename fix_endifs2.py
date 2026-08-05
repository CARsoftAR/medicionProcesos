import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

# We will just replace the broken input tag block with the correct one from the backup

broken_pattern = r'<input type="number" step="any"\s*class="ocr-input-edit text-center celda-valor edit-val \{% if item\.ok == False %\}nok-text\{% else %\}ok-text"\s*value="\{% if item\.val is not None %\}\{\{ item\.val \}\}\{% elif item\.get and item\.get\.val is not None %\}\{\{ item\.get\.val \}\}\{% else %\}\{\{ item \}\}"\s*title="\{% if item\.review %\}ÔÜá´©Å Requiere Revisi├│n Manual"\s*style="font-size: 0\.95rem; font-weight: 800; border-radius: 4px; \{% if item\.review %\}border: 2px solid #f59e0b; background: #fffbeb;\{% else %\}background: rgba\(255,255,255,0\.8\); border: 1px solid #BCCCDC;">'

# Due to potential regex mismatches with encoding issues, we will use a simpler approach.
# We extract everything between `{% for item in row.valores %}` and `{% endfor %}`.

start_marker = '{% for item in row.valores %}'
end_marker = '</td>\n                            {% endfor %}'

start_idx = html.find(start_marker)
# Find the next end_marker
if start_idx != -1:
    end_idx = html.find(end_marker, start_idx) + len(end_marker)
    
    correct_block = '''{% for item in row.valores %}
                            <td class="text-center" style="padding: 0.6rem 0.4rem; border-right: 1px solid var(--stitch-border); background: transparent;">
                                <input type="number" step="any"
                                       class="ocr-input-edit text-center celda-valor edit-val {% if item.ok == False %}nok-text{% else %}ok-text{% endif %}" 
                                       value="{% if item.val is not None %}{{ item.val }}{% elif item.get and item.get.val is not None %}{{ item.get.val }}{% else %}{{ item }}{% endif %}"
                                       title="{% if item.review %}⚠️ Requiere Revisión Manual{% endif %}"
                                       style="font-size: 0.95rem; font-weight: 800; border-radius: 4px; {% if item.review %}border: 2px solid #f59e0b; background: #fffbeb;{% else %}background: rgba(255,255,255,0.8); border: 1px solid #BCCCDC;{% endif %}">
                            </td>
                            {% endfor %}'''
                            
    html = html[:start_idx] + correct_block + html[end_idx:]
    
    with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Replaced matrix values loop with fixed endifs.")
else:
    print("Could not find start marker.")
