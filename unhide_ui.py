import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Fix the Save Button visibility
button_block_regex = r'\{%\s*if success\s*%\}\s*(<button id="btn-importar-sistema".*?</button>)\s*\{%\s*endif\s*%\}'
text = re.sub(button_block_regex, r'\1', text, flags=re.DOTALL)

# 2. Fix the Sidebar Status visibility
sidebar_block_regex = r'\{%\s*if success\s*%\}\s*(<div class="status-card">.*?</div>\s*</div>\s*</div>)\s*\{%\s*endif\s*%\}'
# The status card ends with </div> just before </aside>.
# Let's just do a simpler replace.
status_start = r'\{%\s*if success\s*%\}\s*<div class="status-card">'
text = re.sub(status_start, r'<div class="status-card">', text)
# It ends right before </aside>
status_end = r'</div>\s*\{%\s*endif\s*%\}\s*</aside>'
text = re.sub(status_end, r'</div>\n    </aside>', text)

# Just in case there are double </form> like in line 855: `</form>\n</form>`
text = text.replace('</form>\n</form>', '</form>')

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(text)
print('Removed conditional blocks around button and sidebar.')
