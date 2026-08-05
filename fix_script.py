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
            console.warn(`No se encontró el select con id: ${selectId}`);
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

    document.addEventListener('DOMContentLoaded', function() {
        const btnProcesar = document.getElementById('btn-procesar-json');
        if (btnProcesar) {
            btnProcesar.addEventListener('click', function() {
                console.log('Botón presionado: iniciando procesamiento de JSON.');
                
                const jsonInput = document.getElementById('jsonInput');
                if(!jsonInput) {
                    alert('Falta el campo de texto JSON.');
                    return;
                }
                const jsonStr = jsonInput.value;
                if (!jsonStr.trim()) {
                    alert('Por favor pegá el JSON antes de procesar.');
                    return;
                }
                
                try {
                    JSON.parse(jsonStr);
                } catch (e) {
                    alert('El texto ingresado no es un JSON válido.');
                    return;
                }
                
                showLoader();
                
                const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
                const csrfToken = csrfInput ? csrfInput.value : '';
                
                fetch(window.location.href, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: jsonStr
                })
                .then(async response => {
                    if (!response.ok) {
                        const text = await response.text();
                        throw new Error(`HTTP Error ${response.status}: ${text}`);
                    }
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.indexOf('application/json') !== -1) {
                        return response.json();
                    } else {
                        const text = await response.text();
                        throw new Error(`Expected JSON but got ${contentType}. Body: ${text.substring(0, 200)}...`);
                    }
                })
                .then(data => {
                    hideLoader();
                    if(data.status === 'success') {
                        try {
                            const emptyState = document.getElementById('empty-state');
                            if (emptyState) emptyState.style.display = 'none';
                            
                            const successPanels = document.querySelectorAll('#success-panel');
                            if (successPanels) successPanels.forEach(p => { if (p) p.style.display = 'block'; });
                            
                            const statusOp = document.querySelector('.status-value-op');
                            if(statusOp) statusOp.textContent = '#' + (data.op || '---');
                            else console.warn('Elemento .status-value-op no encontrado');
                            
                            const statusSmall = document.querySelectorAll('.status-value-small');
                            if(statusSmall && statusSmall.length >= 4) {
                                statusSmall[0].textContent = data.proyecto || 'S/P';
                                statusSmall[1].textContent = data.cliente || 'CLIENTE NO DETECTADO';
                                statusSmall[2].textContent = data.denominacion || '---';
                                statusSmall[3].textContent = data.operacion || '---';
                            } else {
                                console.warn('Elementos .status-value-small insuficientes');
                            }
                            
                            selectOptionByText('sel-cliente-ocr', data.cliente);
                            selectOptionByText('sel-proceso-ocr', data.denominacion);
                            selectOptionByText('sel-articulo-ocr', data.articulo);
                            selectOptionByText('sel-elemento-ocr', data.operacion);
                            
                            const tbody = document.getElementById('matrix-body');
                            if (!tbody) {
                                console.warn('Tabla: No se encontró el tbody #matrix-body');
                            } else {
                                tbody.innerHTML = '';
                                
                                const controles = data.controles || [];
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
                                } else {
                                    console.warn('Tabla: No se encontró thead tr');
                                }

                                controles.forEach(row => {
                                    const tr = document.createElement('tr');
                                    tr.className = 'ocr-row';
                                    tr.style = 'border-bottom: 1px solid var(--stitch-border);';
                                    
                                    let valsHtml = '';
                                    let rowVals = row.valores || [];
                                    if(!Array.isArray(rowVals)) {
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
                                    
                                    tr.innerHTML = `
                                        <td class="fw-bold ps-4" style="position: sticky; left: 0; z-index: 20; background: #FFFFFF; border-right: 1px solid var(--stitch-border); white-space: nowrap;">
                                            <input type="text" class="ocr-input-edit text-start edit-control" value="${row.control || ''}" style="font-weight: 700; width: 250px; font-size: 0.8rem;">
                                        </td>
                                        <td class="text-center" style="position: sticky; left: 280px; z-index: 20; background: #FFFFFF;">
                                            <input type="text" class="ocr-input-edit text-center edit-nominal" value="${row.nominal || ''}" style="color: var(--stitch-primary); font-weight: 800; width: 100px; font-size: 0.9rem;">
                                        </td>
                                        <td class="text-center" style="position: sticky; left: 400px; z-index: 20; background: #FFFFFF; border-right: 1px solid var(--stitch-border);">
                                            <input type="text" class="ocr-input-edit text-center edit-tol" value="${row.tolerancia || ''}" style="color: var(--stitch-text); font-weight: 700; width: 140px; font-size: 0.85rem;">
                                        </td>
                                        <td class="text-center" style="position: sticky; left: 560px; z-index: 20; background: #FFFFFF; border-right: 2px solid var(--stitch-border);">
                                            <input type="text" class="ocr-input-edit text-center edit-instr" value="${row.instrumento || ''}" style="font-size: 0.75rem; font-weight: 800; width: 70px;">
                                        </td>
                                        ${valsHtml}
                                    `;
                                    tbody.appendChild(tr);
                                });
                            }
                        } catch (domError) {
                            console.error('Error al inyectar datos en el DOM:', domError);
                            console.error('Datos recibidos del servidor:', data);
                        }
                    } else {
                        console.error('El servidor devolvió un error de aplicación:', data);
                        alert('Error: ' + data.message);
                    }
                })
                .catch(err => {
                    console.error('Fetch o Error de Red/Parseo:', err);
                    alert(`Error en la solicitud: ${err.message}`);
                    hideLoader();
                });
            });
        }
    });
</script>'''

html = html[:script_start] + new_script + html[script_end:]

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Script restored correctly')
