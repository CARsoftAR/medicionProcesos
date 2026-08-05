import re

with open('mediciones/templates/mediciones/ocr_lector_backup_utf8.html', 'r', encoding='utf-8') as f:
    backup_html = f.read()

match = re.search(r'(</form>.*?</main>)', backup_html, re.DOTALL)
main_content = match.group(1)

# Remove ONLY the {% if success %} wraps that hide the UI
main_content = main_content.replace('{% if success %}\n        <div class="status-card">', '<div class="status-card">')
main_content = main_content.replace('        </div>\n        {% endif %}\n    </aside>', '        </div>\n    </aside>')

main_content = main_content.replace('{% if success %}\n                <button id="btn-importar-sistema"', '<button id="btn-importar-sistema"')
main_content = main_content.replace('</button>\n                {% endif %}\n            </div>', '</button>\n            </div>')

main_content = re.sub(
    r'\{%\s*if success\s*%\}\s*<!-- SELECTORES DE VINCULACI\u251c\u2552N -->', 
    '<!-- SELECTORES DE VINCULACI\u251c\u2552N -->', 
    main_content
)
main_content = re.sub(
    r'\{%\s*if success\s*%\}\s*<!-- SELECTORES DE VINCULACIÓN -->', 
    '<!-- SELECTORES DE VINCULACIÓN -->', 
    main_content
)

# Remove the empty state
main_content = re.sub(r'\{%\s*else\s*%\}\s*<!-- ESTADO VAC.*?\{%\s*endif\s*%\}', '', main_content, flags=re.DOTALL)

# Reconstruct the base HTML from backup (everything before </form>)
base_html = backup_html[:backup_html.find('</form>') + 7]

# Wait, we need the textarea instead of file upload!
# Replace the file input and upload-content with the textarea:
file_upload_regex = r'<input type="file" name="plano_pdf" id="plano_pdf".*?</div>\s*<!-- Loader'
textarea_html = '''<div id="upload-content">
                <textarea class="form-control" name="json_data" id="jsonInput" rows="12" placeholder="Pegá aquí el JSON del documento..." style="width: 100%; border: 1px solid var(--stitch-border); border-radius: 8px; padding: 1rem; font-family: 'Fira Code', monospace; font-size: 0.8rem; resize: vertical; margin-bottom: 1rem;"></textarea>
                <button type="button" id="btn-procesar-json" class="btn btn-primary">PROCESAR JSON</button>
            </div>
            <!-- Loader'''
base_html = re.sub(file_upload_regex, textarea_html, base_html, flags=re.DOTALL)

# Also remove the <script> block for the file upload (ajax upload) from the backup
ajax_upload_script = r'<script>\s*function showLoader\(\) \{.*?</script>'
base_html = re.sub(ajax_upload_script, '', base_html, flags=re.DOTALL)

# Let's fix the endifs in the selects that were missing in the BACKUP as well!
main_content = main_content.replace('{% if not auto_matched.cliente_id %}selected>', '{% if not auto_matched.cliente_id %}selected{% endif %}>')
main_content = main_content.replace('{% if c.id == auto_matched.cliente_id %}selected>', '{% if c.id == auto_matched.cliente_id %}selected{% endif %}>')
main_content = main_content.replace('{% if not auto_matched.proceso_id %}selected>', '{% if not auto_matched.proceso_id %}selected{% endif %}>')
main_content = main_content.replace('{% if p.id == auto_matched.proceso_id %}selected>', '{% if p.id == auto_matched.proceso_id %}selected{% endif %}>')
main_content = main_content.replace('{% if not auto_matched.articulo_id %}selected>', '{% if not auto_matched.articulo_id %}selected{% endif %}>')
main_content = main_content.replace('{% if a.id == auto_matched.articulo_id %}selected>', '{% if a.id == auto_matched.articulo_id %}selected{% endif %}>')
main_content = main_content.replace('{% if not auto_matched.elemento_id %}selected>', '{% if not auto_matched.elemento_id %}selected{% endif %}>')
main_content = main_content.replace('{% if e.id == auto_matched.elemento_id %}selected>', '{% if e.id == auto_matched.elemento_id %}selected{% endif %}>')


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

full_html = base_html + '\\n' + main_content + '\n</div>\n' + new_script + '\n{% endblock %}'

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(full_html)
print('Restored EVERYTHING correctly.')
