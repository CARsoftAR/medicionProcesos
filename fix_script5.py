import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(r'<button type="button" id="btn-procesar-json".*?</button>', '<button type="button" id="btn-procesar-json" class="btn btn-primary" onclick="ejecutarProcesamientoJson()">PROCESAR JSON</button>', html)

script_start = html.find('<script>')
script_end = html.rfind('</script>') + 9

new_script = '''<script>
function ejecutarProcesamientoJson() {
    console.log("-> Botón presionado. Leyendo textarea...");

    const textarea = document.getElementById('jsonInput') || document.querySelector('textarea');
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

    // Envío al backend de Django
    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]') ? document.querySelector('[name=csrfmiddlewaretoken]').value : ''
        },
        body: JSON.stringify(jsonData)
    })
    .then(res => res.json())
    .then(data => {
        console.log("<- Respuesta del servidor:", data);
        if (data.status === 'success' || data.cliente) {

            // 1. Rellenar cabecera de forma segura
            if(document.getElementById('clienteField')) document.getElementById('clienteField').value = data.cliente || '';
            if(document.getElementById('proyectoField')) document.getElementById('proyectoField').innerText = data.proyecto || '';
            if(document.getElementById('opField')) document.getElementById('opField').innerText = data.op || '';
            if(document.getElementById('articuloField')) document.getElementById('articuloField').value = data.articulo || '';
            if(document.getElementById('operacionField')) document.getElementById('operacionField').value = data.operacion || '';

            // 2. Rellenar grilla de controles
            const tbody = document.getElementById('tablaControlesBody') || document.querySelector('tbody');
            if (tbody && data.controles) {
                tbody.innerHTML = '';
                data.controles.forEach(item => {
                    let tr = document.createElement('tr');
                    let htmlPiezas = '';
                    if(item.piezas) {
                        for (let p in item.piezas) {
                            htmlPiezas += `<td>${item.piezas[p]}</td>`;
                        }
                    }
                    tr.innerHTML = `
                        <td>${item.cota || ''}</td>
                        <td>${item.nominal || ''}</td>
                        <td>${item.tol || ''}</td>
                        <td>${item.instrumento || ''}</td>
                        ${htmlPiezas}
                    `;
                    tbody.appendChild(tr);
                });
            }

            console.log("¡Interfaz pintada con éxito!");
        } else {
            alert("Error del servidor: " + (data.message || 'Desconocido'));
        }
    })
    .catch(err => {
        console.error("Error en fetch:", err);
        alert("Ocurrió un error al comunicarse con el servidor.");
    });
}
</script>'''

html = html[:script_start] + new_script + html[script_end:]

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Script with EXACT user block applied')
