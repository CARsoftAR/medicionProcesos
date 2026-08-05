import re

with open('mediciones/templates/mediciones/ocr_lector.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the save logic fetch call
old_fetch = '''            fetch("/herramientas/ocr/importar/", {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector("[name=csrfmiddlewaretoken]") ? document.querySelector("[name=csrfmiddlewaretoken]").value : ""
                },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())'''

new_fetch = '''            fetch("{% url 'importar_datos_ocr' %}", {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector("[name=csrfmiddlewaretoken]") ? document.querySelector("[name=csrfmiddlewaretoken]").value : "{{ csrf_token }}"
                },
                body: JSON.stringify(payload)
            })
            .then(async response => {
                if (!response.ok) {
                    const text = await response.text();
                    console.error("Error del servidor (No 200 OK):", text);
                    throw new Error(text);
                }
                return response.json();
            })'''

html = html.replace(old_fetch, new_fetch)

# Update the catch block
old_catch = '''            .catch(error => {
                console.error('Error:', error);
                alert('Error de conexión al importar.');
                btn.disabled = false;
                btn.innerHTML = 'Confirmar e Importar';
            });'''

new_catch = '''            .catch(error => {
                console.error('Error al guardar:', error);
                alert('Error de conexión o fallo del servidor al importar. Revisar consola (F12) para más detalles.');
                btn.disabled = false;
                btn.innerHTML = 'Confirmar e Importar';
            });'''

html = html.replace(old_catch, new_catch)

with open('mediciones/templates/mediciones/ocr_lector.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed save fetch URL and CSRF token.')
