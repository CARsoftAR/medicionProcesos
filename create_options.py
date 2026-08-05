import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace `seleccionarParcial` to auto-append non-existing options
old_seleccionar = '''                    function seleccionarParcial(selectId, textoBuscado) {
                        const select = document.getElementById(selectId);
                        if (!select || !textoBuscado) return;
                        
                        const limpiar = (str) => String(str).toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").trim();
                        const objetivo = limpiar(textoBuscado);
                        console.log(`[Autoseleccion] Buscando '${objetivo}' en ${selectId}`);

                        for (let i = 0; i < select.options.length; i++) {
                            if (!select.options[i].value) continue;
                            const textoOpcion = limpiar(select.options[i].text);
                            const valorOpcion = limpiar(select.options[i].value);
                            
                            if (textoOpcion.includes(objetivo) || objetivo.includes(textoOpcion) || valorOpcion === objetivo) {
                                select.selectedIndex = i;
                                select.dispatchEvent(new Event('change'));
                                if (window.jQuery) jQuery(select).trigger('change');
                                console.log(`[Autoseleccion] ÉXITO en ${selectId}`);
                                break;
                            }
                        }
                    }'''

new_seleccionar = '''                    function seleccionarParcial(selectId, textoBuscado) {
                        const select = document.getElementById(selectId);
                        if (!select || !textoBuscado) return;
                        
                        const limpiar = (str) => String(str).toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").trim();
                        const objetivo = limpiar(textoBuscado);
                        console.log(`[Autoseleccion] Buscando '${objetivo}' en ${selectId}`);

                        let matchFound = false;
                        for (let i = 0; i < select.options.length; i++) {
                            if (!select.options[i].value) continue;
                            const textoOpcion = limpiar(select.options[i].text);
                            const valorOpcion = limpiar(select.options[i].value);
                            
                            if (textoOpcion.includes(objetivo) || objetivo.includes(textoOpcion) || valorOpcion === objetivo) {
                                select.selectedIndex = i;
                                select.dispatchEvent(new Event('change'));
                                if (window.jQuery) jQuery(select).trigger('change');
                                console.log(`[Autoseleccion] ÉXITO en ${selectId}`);
                                matchFound = true;
                                break;
                            }
                        }
                        
                        if (!matchFound) {
                            console.log(`[Autoseleccion] NO EXISTE en ${selectId}. Creando opción dinámica: ${textoBuscado}`);
                            const nuevaOpcion = document.createElement("option");
                            nuevaOpcion.value = ""; // ID vacío para forzar al backend a crearlo
                            nuevaOpcion.text = textoBuscado; // Sin prefijos para que getTextOfSelect lo lea limpio
                            nuevaOpcion.style.fontWeight = "bold";
                            nuevaOpcion.style.color = "var(--stitch-primary)";
                            select.appendChild(nuevaOpcion);
                            select.selectedIndex = select.options.length - 1;
                            select.dispatchEvent(new Event('change'));
                            if (window.jQuery) jQuery(select).trigger('change');
                        }
                    }'''

html = html.replace(old_seleccionar, new_seleccionar)

# Also fix `getTextOfSelect` to ignore "--- Seleccionar ---"
old_getText = '''            function getTextOfSelect(id) {
                const el = document.getElementById(id);
                if(el && el.selectedIndex >= 0) return el.options[el.selectedIndex].text;
                return "";
            }'''

new_getText = '''            function getTextOfSelect(id) {
                const el = document.getElementById(id);
                if(el && el.selectedIndex >= 0) {
                    const txt = el.options[el.selectedIndex].text;
                    if (txt.includes("---") || txt.toLowerCase().includes("seleccionar")) return "";
                    return txt;
                }
                return "";
            }'''

html = html.replace(old_getText, new_getText)

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Updated script for dynamic option creation.')
