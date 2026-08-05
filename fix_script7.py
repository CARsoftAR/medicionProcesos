import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

script_start = html.find('<script>')
script_end = html.rfind('</script>') + 9

new_script = '''<script>
function showLoader() {
    const loader = document.getElementById('processing-loader');
    const upload = document.getElementById('upload-content');
    if (loader) loader.style.display = 'block';
    if (upload) upload.style.display = 'none';
}

function hideLoader() {
    const loader = document.getElementById('processing-loader');
    const upload = document.getElementById('upload-content');
    if (loader) loader.style.display = 'none';
    if (upload) upload.style.display = 'block';
}

function selectOptionByText(selectId, text) {
    const sel = document.getElementById(selectId);
    if(!sel) {
        console.warn("No se encontró el select con id: " + selectId);
        return;
    }
    if(!text) return;
    text = text.toString().toUpperCase().trim();
    for(let i=0; i<sel.options.length; i++) {
        if(sel.options[i].text.toUpperCase().includes(text)) {
            sel.selectedIndex = i;
            return;
        }
    }
}

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

            showLoader();

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
                hideLoader();
                console.log("DATOS JSON RECIBIDOS:", data);
                
                if (data.status === "success" || data.cliente) {
                    // Activar el panel visual
                    const emptyState = document.getElementById('empty-state');
                    if (emptyState) emptyState.style.display = 'none';
                    
                    const successPanels = document.querySelectorAll('#success-panel');
                    if (successPanels) successPanels.forEach(p => { if (p) p.style.display = 'block'; });

                    // Alinear con los IDs reales del DOM
                    const statusOp = document.querySelector('.status-value-op');
                    if(statusOp) statusOp.textContent = '#' + (data.op || '---');
                    
                    const statusSmall = document.querySelectorAll('.status-value-small');
                    if(statusSmall && statusSmall.length >= 4) {
                        statusSmall[0].textContent = data.proyecto || 'S/P';
                        statusSmall[1].textContent = data.cliente || 'CLIENTE NO DETECTADO';
                        statusSmall[2].textContent = data.denominacion || '---';
                        statusSmall[3].textContent = data.operacion || '---';
                    }
                    
                    selectOptionByText('sel-cliente-ocr', data.cliente);
                    selectOptionByText('sel-proceso-ocr', data.denominacion);
                    selectOptionByText('sel-articulo-ocr', data.articulo);
                    selectOptionByText('sel-elemento-ocr', data.operacion);

                    const tbody = document.getElementById("matrix-body");
                    if (tbody && data.controles) {
                        tbody.innerHTML = "";
                        
                        // Asegurar que las columnas de piezas de la cabecera existan
                        const piezas = data.piezas || ['1','2','3','4','5','6','7','8','9','10'];
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

                        data.controles.forEach(row => {
                            let tr = document.createElement("tr");
                            tr.className = 'ocr-row';
                            tr.style = 'border-bottom: 1px solid var(--stitch-border);';
                            
                            let valsHtml = '';
                            let rowVals = row.valores || row.piezas || [];
                            if(!Array.isArray(rowVals) && typeof rowVals === 'object') {
                                // If row.valores/piezas is an object mapping indices to values
                                rowVals = piezas.map(p => rowVals[p] || '');
                            }
                            
                            rowVals.forEach(vItem => {
                                let valStr = '';
                                let isOk = true;
                                if(vItem !== null && typeof vItem === 'object') {
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
                hideLoader();
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
print('Script with real DOM elements applied')
