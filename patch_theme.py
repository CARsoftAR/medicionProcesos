import re

with open('mediciones/templates/mediciones/estadisticas_control.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update CSS
old_css = """    :root {
        --stitch-primary: #e11d48;     /* Rose 600 */
        --stitch-secondary: #fda4af;   /* Rose 300 */
        --stitch-bg: #fdf2f8;          /* Rose 50 */
        --stitch-text: #1e293b;        /* Slate 800 */
        --stitch-glass: rgba(255, 255, 255, 0.9);
        --stitch-border: rgba(225, 29, 72, 0.15);
        --stitch-shadow: 0 10px 40px -10px rgba(225, 29, 72, 0.08);
    }"""

new_css = """    :root {
        --stitch-primary: #e11d48;
        --stitch-secondary: #fda4af;
        --stitch-bg: #fdf2f8;
        --stitch-text: #1e293b;
        --stitch-glass: rgba(255, 255, 255, 0.9);
        --stitch-border: rgba(225, 29, 72, 0.15);
        --stitch-shadow: 0 10px 40px -10px rgba(225, 29, 72, 0.08);
        --stitch-btn-shadow: 0 4px 6px -1px rgba(225, 29, 72, 0.3);
    }
    
    :root.theme-danger {
        --stitch-primary: #e11d48;
        --stitch-secondary: #fda4af;
        --stitch-bg: #fdf2f8;
        --stitch-border: rgba(225, 29, 72, 0.15);
        --stitch-shadow: 0 10px 40px -10px rgba(225, 29, 72, 0.08);
        --stitch-btn-shadow: 0 4px 6px -1px rgba(225, 29, 72, 0.3);
    }
    
    :root.theme-warning {
        --stitch-primary: #d97706;     /* Amber 600 */
        --stitch-secondary: #fcd34d;   /* Amber 300 */
        --stitch-bg: #fffbeb;          /* Amber 50 */
        --stitch-border: rgba(217, 119, 6, 0.15);
        --stitch-shadow: 0 10px 40px -10px rgba(217, 119, 6, 0.08);
        --stitch-btn-shadow: 0 4px 6px -1px rgba(217, 119, 6, 0.3);
    }

    :root.theme-success {
        --stitch-primary: #059669;     /* Emerald 600 */
        --stitch-secondary: #6ee7b7;   /* Emerald 300 */
        --stitch-bg: #ecfdf5;          /* Emerald 50 */
        --stitch-border: rgba(5, 150, 105, 0.15);
        --stitch-shadow: 0 10px 40px -10px rgba(5, 150, 105, 0.08);
        --stitch-btn-shadow: 0 4px 6px -1px rgba(5, 150, 105, 0.3);
    }"""
html = html.replace(old_css, new_css)

# 2. Update inline styles that use #e11d48 hardcoded
html = html.replace("color: #e11d48;", "color: var(--stitch-primary);")
html = html.replace("background-color: var(--stitch-primary, #e11d48); color: white; padding: 0.6rem 1.5rem; border-radius: 14px; font-size: 0.9rem; font-family: 'Outfit', sans-serif; font-weight: 800; text-decoration: none; display: flex; align-items: center; gap: 0.5rem; transition: all 0.2s; box-shadow: 0 4px 6px -1px rgba(225, 29, 72, 0.3);", 
                    "background-color: var(--stitch-primary); color: white; padding: 0.6rem 1.5rem; border-radius: 14px; font-size: 0.9rem; font-family: 'Outfit', sans-serif; font-weight: 800; text-decoration: none; display: flex; align-items: center; gap: 0.5rem; transition: all 0.2s; box-shadow: var(--stitch-btn-shadow);")
html = html.replace("color: var(--stitch-primary, #e11d48);", "color: var(--stitch-primary);")
html = html.replace("background: var(--stitch-primary, #e11d48);", "background: var(--stitch-primary);")

# 3. Add applyDynamicTheme to JS
js_logic = """    function applyDynamicTheme(cp, cpk) {
        let worst = null;
        const vals = [];
        if (cp !== null && cp !== undefined && !isNaN(cp)) vals.push(parseFloat(cp));
        if (cpk !== null && cpk !== undefined && !isNaN(cpk)) vals.push(parseFloat(cpk));
        
        if (vals.length > 0) {
            worst = Math.min(...vals);
        }

        let theme = 'danger'; // Default if missing is red
        if (worst !== null) {
            if (worst < 1.0) theme = 'danger';
            else if (worst < 1.33) theme = 'warning';
            else theme = 'success';
        }
        
        const root = document.documentElement;
        root.classList.remove('theme-danger', 'theme-warning', 'theme-success');
        root.classList.add(`theme-${theme}`);
    }

    document.addEventListener('DOMContentLoaded', () => {"""
html = html.replace("    document.addEventListener('DOMContentLoaded', () => {", js_logic)

# 4. Call applyDynamicTheme on page load
page_load_call = """            // Logic to select default chart based on control type
            applyDynamicTheme(DATA.stats.cp, DATA.stats.cpk);
"""
html = html.replace("            // Logic to select default chart based on control type\n", page_load_call)

# 5. Call applyDynamicTheme on AJAX loadControlData
ajax_call = """            DATA.stats = data.stats; DATA.points = data.data_points; DATA.labels = data.labels;
            applyDynamicTheme(data.stats.cp, data.stats.cpk);
"""
html = html.replace("            DATA.stats = data.stats; DATA.points = data.data_points; DATA.labels = data.labels;\n", ajax_call)

with open('mediciones/templates/mediciones/estadisticas_control.html', 'w', encoding='utf-8') as f:
    f.write(html)
    
print("Dynamic theme applied.")
