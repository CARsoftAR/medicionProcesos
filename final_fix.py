import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

# I will rewrite the JS block completely. I'll make sure there is no syntax error and it correctly handles the selects and the table.

script_start = html.rfind('<script>')
script_end = html.rfind('</script>') + 9

new_script = '''<script>
window.currentOcrData = null;

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
                
                let paginaDatos = data;
                if (data.paginas && Array.isArray(data.paginas) && data.paginas.length > 0) {
                    paginaDatos = data.paginas[0];
                    console.log("Usando datos de la página 1:", paginaDatos);
                }
                
                window.currentOcrData = paginaDatos;

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
                    
                    function seleccionarParcial(selectId, textoBuscado) {
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
                    }

                    seleccionarParcial('sel-cliente-ocr', paginaDatos.cliente || data.cliente);
                    seleccionarParcial('sel-proceso-ocr', paginaDatos.denominacion || data.denominacion);
                    seleccionarParcial('sel-articulo-ocr', paginaDatos.articulo || data.articulo);
                    seleccionarParcial('sel-elemento-ocr', paginaDatos.operacion || data.operacion);

                    const tbody = document.querySelector("#tabla-ocr-resultados tbody");
                    if (tbody && (paginaDatos.controles || data.controles)) {
                        tbody.innerHTML = "";
                        const controlesData = paginaDatos.controles || data.controles || [];
                        let piezasOriginales = paginaDatos.piezas || data.piezas;
                        let arrayPiezas = [];
                        
                        if (piezasOriginales && Array.isArray(piezasOriginales)) {
                            arrayPiezas = piezasOriginales;
                        } else if (piezasOriginales && typeof piezasOriginales === 'object') {
                            arrayPiezas = Object.keys(piezasOriginales);
                        } else {
                            // If no pieces defined, assume 10 pieces or whatever we have values for
                            let maxVals = 10;
                            controlesData.forEach(c => {
                                if (c.valores && Array.isArray(c.valores) && c.valores.length > maxVals) {
                                    maxVals = c.valores.length;
                                } else if (c.piezas && typeof c.piezas === 'object') {
                                    const ks = Object.keys(c.piezas).map(k => parseInt(k)).filter(n => !isNaN(n));
                                    if(ks.length > 0) maxVals = Math.max(maxVals, ...ks);
                                }
                            });
                            arrayPiezas = Array.from({length: maxVals}, (_, i) => (i + 1).toString());
                        }

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
                                if (row.piezas && row.piezas[p] !== undefined) {
                                    vItem = row.piezas[p];
                                } else if (row.valores && typeof row.valores === 'object' && !Array.isArray(row.valores)) {
                                    vItem = row.valores[p] || '';
                                } else if (row.valores && Array.isArray(row.valores)) {
                                    vItem = row.valores[idx] || '';
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
    }

    const btnGuardar = document.getElementById('btn-importar-sistema');
    if (btnGuardar) {
        btnGuardar.addEventListener('click', function() {
            if (!window.currentOcrData) {
                alert("Primero debe procesar un JSON válido antes de confirmar.");
                return;
            }

            const header = window.currentOcrData.header || window.currentOcrData || {};
            
            function getTextOfSelect(id) {
                const el = document.getElementById(id);
                if(el && el.selectedIndex >= 0) return el.options[el.selectedIndex].text;
                return "";
            }
            
            header.cliente = getTextOfSelect('sel-cliente-ocr') || header.cliente;
            header.denominacion = getTextOfSelect('sel-proceso-ocr') || header.denominacion;
            header.articulo = getTextOfSelect('sel-articulo-ocr') || header.articulo;
            header.operacion = getTextOfSelect('sel-elemento-ocr') || header.operacion;
            
            const matrix = [];
            const ths = document.querySelectorAll('.table-ocr thead tr th');
            const piezasCols = [];
            for (let i = 4; i < ths.length; i++) {
                piezasCols.push(ths[i].textContent.trim());
            }

            document.querySelectorAll('.ocr-row').forEach(tr => {
                const rowData = {
                    control: tr.querySelector('.edit-control').value,
                    nominal: tr.querySelector('.edit-nominal').value,
                    tolerancia: tr.querySelector('.edit-tol').value,
                    instrumento: tr.querySelector('.edit-instr').value,
                    valores: []
                };
                
                tr.querySelectorAll('.edit-val').forEach(input => {
                    rowData.valores.push(input.value);
                });
                
                matrix.push(rowData);
            });
            
            const payload = {
                header: header,
                piezas: piezasCols.length > 0 ? piezasCols : (window.currentOcrData.piezas || []), 
                matrix: matrix,
                proceso_id: document.getElementById('sel-proceso-ocr').value,
                articulo_id: document.getElementById('sel-articulo-ocr').value,
                elemento_id: document.getElementById('sel-elemento-ocr').value,
                cliente_id: document.getElementById('sel-cliente-ocr').value
            };

            const btn = this;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Guardando...';

            fetch("/herramientas/ocr/importar/", {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector("[name=csrfmiddlewaretoken]") ? document.querySelector("[name=csrfmiddlewaretoken]").value : ""
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            title: '¡PROCESO COMPLETADO!',
                            html: `
                                <div class="swal-success-container">
                                    <div class="swal-success-icon"><i class="ri-checkbox-circle-fill"></i></div>
                                    <div class="swal-success-title">Importación Exitosa</div>
                                    <div class="swal-success-text">Los datos han sido vinculados correctamente a la <b>OP ${data.op}</b>.</div>
                                    <div class="swal-success-footer">Redirigiendo al panel de mediciones...</div>
                                </div>
                            `,
                            showConfirmButton: false,
                            timer: 3000,
                            timerProgressBar: true,
                            background: 'var(--stitch-glass)',
                            backdrop: 'rgba(30, 41, 59, 0.4)',
                        }).then(() => {
                            window.location.href = `/mediciones/nueva/?op=${data.op}&proy=${encodeURIComponent(data.proy)}&proc=${data.proc_id}`;
                        });
                    } else {
                        alert(`¡Importación Exitosa! Los datos se vincularon a la OP ${data.op}. Redirigiendo...`);
                        window.location.href = `/mediciones/nueva/?op=${data.op}&proy=${encodeURIComponent(data.proy)}&proc=${data.proc_id}`;
                    }
                } else {
                    alert('Error: ' + data.message);
                    btn.disabled = false;
                    btn.innerHTML = 'Confirmar e Importar';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error de conexión al importar.');
                btn.disabled = false;
                btn.innerHTML = 'Confirmar e Importar';
            });
        });
    }
});
</script>'''

html = html[:script_start] + new_script + html[script_end:]

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed script to draw table perfectly and submit properly.')
