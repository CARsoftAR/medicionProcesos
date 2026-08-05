import re

with open('mediciones/templates/mediciones/ocr_lector_backup_utf8.html', 'r', encoding='utf-8') as f:
    backup_html = f.read()

# Extract the save script from the backup
save_script_regex = r'(\s*document\.getElementById\(\'btn-importar-sistema\'\)\.addEventListener.*?\}\);)'
match = re.search(save_script_regex, backup_html, flags=re.DOTALL)
save_script = match.group(1) if match else None

if save_script:
    with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    # We will inject the save_script right before `});\n</script>`
    # BUT wait, `save_script` in the backup was standalone, using `{% if success %}`.
    # We don't need `{% if success %}` because we want it available always.
    
    # We will wrap it in an addEventListener if it's not already. In the backup it was standalone.
    # Wait, the `save_script` uses `const header = JSON.parse('{{ header_json|escapejs }}');`.
    # BUT if the user is pasting JSON, there is NO `{{ header_json|escapejs }}` from Django context!
    # The header must be extracted from the JSON that was just parsed, OR from the DOM, OR we can store the parsed JSON in a global variable `window.lastParsedJSON` when the JSON is processed!
    
    pass
