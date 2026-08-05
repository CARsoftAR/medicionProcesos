import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the function `seleccionarValorPorTextoOId` to be extremely robust and add console.logs for debugging

old_func = '''                    function seleccionarValorPorTextoOId(selectId, valorBuscado) {
                        const select = document.getElementById(selectId);
                        if (!select || !valorBuscado) return;
                        
                        let valorStr = String(valorBuscado).trim().toLowerCase();
                        
                        for (let i = 0; i < select.options.length; i++) {
                            let optText = select.options[i].text.trim().toLowerCase();
                            let optVal = select.options[i].value.toString().trim().toLowerCase();
                            
                            if (optVal === valorStr || optText === valorStr || optText.includes(valorStr) || valorStr.includes(optText)) {
                                select.selectedIndex = i;
                                // Disparar change event nativo
                                select.dispatchEvent(new Event('change'));
                                // Si en el futuro usan select2
                                if (window.jQuery) {
                                    jQuery(select).trigger('change');
                                }
                                break;
                            }
                        }
                    }'''

new_func = '''                    function seleccionarValorPorTextoOId(selectId, valorBuscado) {
                        const select = document.getElementById(selectId);
                        if (!select || !valorBuscado) {
                            console.log(`[Autoselect] Saltando ${selectId}: valor nulo o elemento inexistente.`);
                            return;
                        }
                        
                        let valorStr = String(valorBuscado).trim().toLowerCase();
                        console.log(`[Autoselect] Buscando '${valorStr}' en ${selectId}`);
                        
                        let matchFound = false;
                        for (let i = 0; i < select.options.length; i++) {
                            let optText = select.options[i].text.trim().toLowerCase();
                            let optVal = select.options[i].value.toString().trim().toLowerCase();
                            
                            if (optVal === valorStr || optText === valorStr || optText.includes(valorStr) || valorStr.includes(optText)) {
                                select.selectedIndex = i;
                                console.log(`[Autoselect] ÉXITO en ${selectId}: Asignado a '${optText}' (index ${i})`);
                                matchFound = true;
                                select.dispatchEvent(new Event('change'));
                                if (window.jQuery) {
                                    jQuery(select).trigger('change');
                                }
                                break;
                            }
                        }
                        if (!matchFound) {
                            console.log(`[Autoselect] FRACASO en ${selectId}: Ninguna de las ${select.options.length} opciones coincidió con '${valorStr}'.`);
                        }
                    }'''

html = html.replace(old_func, new_func)

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Updated autoselect function.')
