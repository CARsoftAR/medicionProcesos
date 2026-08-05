import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

script_start = html.rfind('<script>')
script_end = html.rfind('</script>') + 9

new_script = '''<script>
document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("btn-procesar-json");
    if (btn) {
        btn.addEventListener("click", function () {
            console.log("-> Botón clickeado mediante addEventListener seguro.");

            const textarea = document.getElementById("jsonInput") || document.querySelector("textarea");
            if (!textarea) {
                alert("No se encontró el campo de texto.");
                return;
            }

            let rawText = textarea.value.trim();
            if (!rawText) {
                alert("El campo de texto está vacío.");
                return;
            }

            let jsonData;
            try {
                jsonData = JSON.parse(rawText);
            } catch (e) {
                alert("Error de sintaxis en el JSON: " + e.message);
                return;
            }

            fetch(window.location.href, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]") ? document.querySelector("[name=csrfmiddlewaretoken]").value : ""
                },
                body: JSON.stringify(jsonData)
            })
            .then(res => {
                if (!res.ok) {
                    return res.text().then(text => { throw new Error("HTTP " + res.status + ": " + text) });
                }
                return res.json();
            })
            .then(data => {
                console.log("DATOS JSON RECIBIDOS:", data);
                
                // Mapeo seguro si viene encapsulado en 'paginas'
                let paginaDatos = data;
                if (data.paginas && Array.isArray(data.paginas) && data.paginas.length > 0) {
                    paginaDatos = data.paginas[0];
                    console.log("Usando datos de la página 1:", paginaDatos);
                }

                if (paginaDatos.status === "success" || paginaDatos.cliente || data.status === "success") {
                    const statusOp = document.querySelector('.status-value-op');
                    if(statusOp) statusOp.textContent = '#' + (paginaDatos.op || data.op || '---');
                    
                    const statusSmall = document.querySelectorAll('.status-value-small');
                    if(statusSmall && statusSmall.length >= 4) {
                        statusSmall[0].textContent = paginaDatos.proyecto || data.proyecto || 'S/P';
                        statusSmall[1].textContent = paginaDatos.cliente || data.cliente || 'CLIENTE NO DETECTADO';
                        statusSmall[2].textContent = paginaDatos.denominacion || data.denominacion || '---';
                        statusSmall[3].textContent = paginaDatos.operacion || data.operacion || '---';
                    }
                    
                    function seleccionarValorPorTextoOId(selectId, valorBuscado) {
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
                    }

                    seleccionarValorPorTextoOId('sel-cliente-ocr', paginaDatos.cliente || data.cliente);
                    seleccionarValorPorTextoOId('sel-proceso-ocr', paginaDatos.denominacion || data.denominacion);
                    seleccionarValorPorTextoOId('sel-articulo-ocr', paginaDatos.articulo || data.articulo);
                    seleccionarValorPorTextoOId('sel-elemento-ocr', paginaDatos.operacion || data.operacion);

                    const tbody = document.querySelector("#tabla-ocr-resultados tbody");
                    if (tbody && (paginaDatos.controles || data.controles)) {
                        tbody.innerHTML = "";
                        
                        const controlesData = paginaDatos.controles || data.controles || [];
                        const piezas = paginaDatos.piezas || data.piezas || ['1','2','3','4','5','6','7','8','9','10'];
                        const theadRow = document.querySelector('.table-ocr thead tr');
                        if (theadRow) {
                            while(theadRow.children.length > 4) {
                                theadRow.removeChild(theadRow.lastChild);
                            }
                            piezas.forEach(p => {
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
                            
                            // Mapeo dinámico por clave de pieza {"1": "1276", "6": "12,80"} o valores secuenciales
                            piezas.forEach(p => {
                                let vItem = '';
                                if (row.piezas && row.piezas[p] !== undefined) {
                                    vItem = row.piezas[p];
                                } else if (row.valores && Array.isArray(row.valores)) {
                                    // Fallback if it's an array
                                    vItem = row.valores[piezas.indexOf(p)] || '';
                                } else if (row.valores && typeof row.valores === 'object') {
                                    vItem = row.valores[p] || '';
                                }

                                let valStr = '';
                                let isOk = true;
                                if (vItem !== null && typeof vItem === 'object') {
                                    valStr = vItem.val || '';
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
                    console.log("¡Interfaz pintada con éxito!");
                    alert("Datos cargados correctamente en consola. Ver F12");
                } else {
                    alert("Error del servidor: " + (data.message || "Desconocido"));
                }
            })
            .catch(err => {
                console.error("Error en fetch:", err);
                alert("Ocurrió un error al comunicarse con el servidor: " + err.message);
            });
        });
    } else {
        console.error("No se encontró el botón btn-procesar-json en el DOM.");
    }
});
</script>'''

html = html[:script_start] + new_script + html[script_end:]

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('JS autoselect functionality updated.')
