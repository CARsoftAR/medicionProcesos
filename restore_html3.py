import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    current_html = f.read()

with open('mediciones/templates/mediciones/ocr_lector_backup_utf8.html', 'r', encoding='utf-8') as f:
    backup_html = f.read()

# Grab main content from backup
match = re.search(r'(</form>.*?</main>)', backup_html, re.DOTALL)
main_content = match.group(1)

# Now, we manually remove ONLY the {% if success %} blocks that conditionally hide the main components.
# Specifically, we want to remove:
# - {% if success %}
# - {% else %}
# - {% endif %} 
# BUT ONLY IF they stand alone on their own lines (which they do in the layout), 
# to avoid breaking inline tags like {% if not auto_matched.cliente_id %}selected{% endif %}.

lines = main_content.split('\n')
clean_lines = []
skip_else_block = False

for line in lines:
    stripped = line.strip()
    if stripped == '{% if success %}':
        # Just remove this line
        continue
    elif stripped == '{% else %}':
        # We start skipping lines until the next {% endif %}, because this is the "empty state" which we don't want to show
        # Wait, the empty state (Esperando Documento) might be useful? No, we don't want it blocking the view.
        skip_else_block = True
        continue
    elif stripped == '{% endif %}':
        if skip_else_block:
            skip_else_block = False
            continue
        # If it's just a closing endif for a success block we removed, remove it
        # BUT if it closes something else (like {% if header.ai_error_msg ... %}), we MUST KEEP IT.
        # How do we know? We can just keep it if it's not closing `success`.
        # Actually, in the backup, `{% if header... %}` has its own `{% endif %}`.
        # The `{% if success %}` blocks are:
        # 1. After </form> for sidebar (ends before </aside>)
        # 2. Around btn-importar-sistema (ends right after)
        # 3. Around the verification-bar and matrix-card (has an else, ends after empty state)
        
        # This is getting too complex to guess.
        pass
        
    if not skip_else_block:
        clean_lines.append(line)

main_content = '\n'.join(clean_lines)

# Fix the stray endifs left by the simplistic removal of `{% if success %}`
main_content = main_content.replace('''</aside>
    <!-- MAIN CONTENT -->
    <main class="main-content-ocr">
        <div class="header-actions">
            <h2 class="panel-title">Panel de Verificaci├│n</h2>
            <div class="d-flex align-items-center gap-2">
                <button class="btn-descartar" onclick="location.reload();">Descartar</button>
                
                <button id="btn-importar-sistema" class="btn-confirmar">Confirmar e Importar</button>
                {% endif %}
            </div>
        </div>''', '''</aside>
    <!-- MAIN CONTENT -->
    <main class="main-content-ocr">
        <div class="header-actions">
            <h2 class="panel-title">Panel de Verificaci├│n</h2>
            <div class="d-flex align-items-center gap-2">
                <button class="btn-descartar" onclick="location.reload();">Descartar</button>
                <button id="btn-importar-sistema" class="btn-confirmar">Confirmar e Importar</button>
            </div>
        </div>''')

main_content = main_content.replace('''    </aside>''', '''    {% endif %}</aside>''')
# Wait, let's just do an exact string replace to be 100% safe.
