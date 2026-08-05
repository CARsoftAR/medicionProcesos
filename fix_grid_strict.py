import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

script_start = html.rfind('const tbody = document.querySelector("#tabla-ocr-resultados tbody");')
script_end = html.rfind('console.log("¡Interfaz pintada con éxito!");')

old_table_logic = html[script_start:script_end]

new_table_logic = '''const tbody = document.querySelector("#tabla-ocr-resultados tbody");
                    if (tbody && (paginaDatos.controles || data.controles)) {
                        tbody.innerHTML = "";
                        const controlesData = paginaDatos.controles || data.controles || [];
                        
                        // Extraer todas las claves únicas (piezas) presentes en el JSON
                        let uniqueKeys = new Set();
                        
                        if (paginaDatos.piezas && Array.isArray(paginaDatos.piezas) && paginaDatos.piezas.length > 0) {
                            paginaDatos.piezas.forEach(p => uniqueKeys.add(p.toString()));
                        } else {
                            controlesData.forEach(c => {
                                if (c.piezas && typeof c.piezas === 'object') {
                                    Object.keys(c.piezas).forEach(k => uniqueKeys.add(k));
                                }
                            });
                        }
                        
                        // Si no hay ninguna pieza, fallback a ["1"] por seguridad
                        if (uniqueKeys.size === 0) {
                            uniqueKeys.add("1");
                        }
                        
                        // Convertir a array y ordenar numéricamente (por ejemplo: "1", "6", "14", "26_1")
                        let arrayPiezas = Array.from(uniqueKeys).sort((a, b) => {
                            let numA = parseFloat(a.replace(/_/g, '.'));
                            let numB = parseFloat(b.replace(/_/g, '.'));
                            if (isNaN(numA)) numA = 0;
                            if (isNaN(numB)) numB = 0;
                            return numA - numB;
                        });

                        const theadRow = document.querySelector('.table-ocr thead tr');
                        if (theadRow) {
                            while(theadRow.children.length > 4) {
                                theadRow.removeChild(theadRow.lastChild);
                            }
                            arrayPiezas.forEach(p => {
                                const th = document.createElement('th');
                                th.className = 'text-center';
                                th.style = 'width: 85px; min-width: 85px; color: var(--stitch-primary); font-size: 0.8rem; font-weight: 800; padding: 0.5rem 0; border-bottom: 2px solid var(--stitch-border); background: #F8FAFC;';
                                th.textContent = p;
                                theadRow.appendChild(th);
                            });
                        }

                        controlesData.forEach(row => {
                            let tr = document.createElement("tr");
                            tr.className = 'ocr-row';
                            tr.style = 'border-bottom: 1px solid var(--stitch-border);';
                            
                            let valsHtml = '';
                            arrayPiezas.forEach((p, idx) => {
                                let vItem = '';
                                
                                if (row.piezas && typeof row.piezas === 'object') {
                                    vItem = row.piezas[p];
                                } else if (row.valores && Array.isArray(row.valores)) {
                                    if(idx < row.valores.length) vItem = row.valores[idx] || '';
                                }

                                let valStr = '';
                                let isOk = true;
                                if (vItem !== null && typeof vItem === 'object') {
                                    valStr = vItem.val !== undefined ? vItem.val : '';
                                    isOk = vItem.ok !== false;
                                } else {
                                    valStr = vItem || '';
                                }
                                
                                const colorClass = isOk ? 'ok-text' : 'nok-text';
                                valsHtml += `<td class="text-center" style="padding: 0.6rem 0.4rem; border-right: 1px solid var(--stitch-border); background: transparent;">
                                    <input type="text" class="ocr-input-edit text-center celda-valor edit-val ${colorClass}" value="${valStr}" style="font-size: 0.95rem; font-weight: 800; border-radius: 4px; background: rgba(255,255,255,0.8); border: 1px solid #BCCCDC;">
                                </td>`;
                            });

                            const cotaName = row.cota || row.control || '';
                            const nominalVal = row.nominal || '';
                            const tolVal = row.tol || row.tolerancia || '';
                            const instrVal = row.instrumento || '';

                            tr.innerHTML = `
                                <td class="fw-bold ps-4" style="position: sticky; left: 0; z-index: 20; background: #FFFFFF; border-right: 1px solid var(--stitch-border); white-space: nowrap;">
                                    <input type="text" class="ocr-input-edit text-start edit-control" value="${cotaName}" style="font-weight: 700; width: 250px; font-size: 0.8rem;">
                                </td>
                                <td class="text-center" style="position: sticky; left: 280px; z-index: 20; background: #FFFFFF;">
                                    <input type="text" class="ocr-input-edit text-center edit-nominal" value="${nominalVal}" style="color: var(--stitch-primary); font-weight: 800; width: 100px; font-size: 0.9rem;">
                                </td>
                                <td class="text-center" style="position: sticky; left: 400px; z-index: 20; background: #FFFFFF; border-right: 1px solid var(--stitch-border);">
                                    <input type="text" class="ocr-input-edit text-center edit-tol" value="${tolVal}" style="color: var(--stitch-text); font-weight: 700; width: 140px; font-size: 0.85rem;">
                                </td>
                                <td class="text-center" style="position: sticky; left: 560px; z-index: 20; background: #FFFFFF; border-right: 2px solid var(--stitch-border);">
                                    <input type="text" class="ocr-input-edit text-center edit-instr" value="${instrVal}" style="font-size: 0.75rem; font-weight: 800; width: 70px;">
                                </td>
                                ${valsHtml}
                            `;
                            tbody.appendChild(tr);
                        });
                    }
                    '''

html = html.replace(old_table_logic, new_table_logic)

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed grid to be exactly mapped without blind generation.')
