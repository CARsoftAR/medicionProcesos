import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    current_html = f.read()

with open('mediciones/templates/mediciones/ocr_lector_backup_utf8.html', 'r', encoding='utf-8') as f:
    backup_html = f.read()

match = re.search(r'(</form>.*?</main>)', backup_html, re.DOTALL)
main_content = match.group(1)

loader_end_match = re.search(r'(</div>\s*<script>)', current_html)
if loader_end_match:
    loader_end_idx = loader_end_match.start()
    base_html = current_html[:loader_end_idx] + '</div>\n'
else:
    base_html = current_html.split('<script>')[0]

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
                
                if (data.status === "success" || data.cliente) {
                    const statusOp = document.querySelector('.status-value-op');
                    if(statusOp) statusOp.textContent = '#' + (data.op || '---');
                    
                    const statusSmall = document.querySelectorAll('.status-value-small');
                    if(statusSmall && statusSmall.length >= 4) {
                        statusSmall[0].textContent = data.proyecto || 'S/P';
                        statusSmall[1].textContent = data.cliente || 'CLIENTE NO DETECTADO';
                        statusSmall[2].textContent = data.denominacion || '---';
                        statusSmall[3].textContent = data.operacion || '---';
                    }
                    
                    function selectOptionByText(selectId, text) {
                        const sel = document.getElementById(selectId);
                        if(!sel || !text) return;
                        text = text.toString().toUpperCase().trim();
                        for(let i=0; i<sel.options.length; i++) {
                            if(sel.options[i].text.toUpperCase().includes(text)) {
                                sel.selectedIndex = i;
                                return;
                            }
                        }
                    }

                    selectOptionByText('sel-cliente-ocr', data.cliente);
                    selectOptionByText('sel-proceso-ocr', data.denominacion);
                    selectOptionByText('sel-articulo-ocr', data.articulo);
                    selectOptionByText('sel-elemento-ocr', data.operacion);

                    const tbody = document.querySelector("#tabla-ocr-resultados tbody");
                    if (tbody && data.controles) {
                        tbody.innerHTML = "";
                        
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
                                leftTr = theadRow.appendChild(th);
                            });
                        }

                        data.controles.forEach(row => {
                            let tr = document.createElement("tr");
                            tr.className = 'ocr-row';
                            tr.style = 'border-bottom: 1px solid var(--stitch-border);';
                            
                            let valsHtml = '';
                            let rowVals = row.valores || row.piezas || [];
                            if(!Array.isArray(rowVals) && typeof rowVals === 'object') {
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
                console.error("Error en fetch:", err);
                alert("Ocurrió un error al comunicarse con el servidor: " + err.message);
            });
        });
    } else {
        console.error("No se encontró el botón btn-procesar-json en el DOM.");
    }
});
</script>'''

# Let's remove ONLY the {% if success %} and corresponding {% endif %} blocks that hide the sidebar and main-content, 
# not all of them.
# There is an {% if success %} right after </form>. Let's regex it.
main_content = re.sub(r'\{%\s*if\s+success\s*%\}(.*?)\{%\s*endif\s*%\}', r'\1', main_content, flags=re.DOTALL)
# Actually, the main_content might have nested endifs (e.g., inside the options). The greedy/non-greedy regex might mess up.
# Better to be explicit: find the exact lines:
# {% if success %}
# {% endif %}

main_content_lines = main_content.split('\n')
clean_lines = []
for line in main_content_lines:
    # Delete the standalone `{% if success %}` lines
    if line.strip() == '{% if success %}' or line.strip() == '{% else %}' or line.strip() == '{% endif %}':
        # But wait, there's `{% if header.ai_error_msg or error_ia %}`! We shouldn't delete all endifs.
        pass
    else:
        clean_lines.append(line)
# Wait, if I delete all `{% endif %}`, it will break `{% if header.ai_error_msg ... %}`!
# I will just write a careful regex for exactly the `{% if success %}` ones.
