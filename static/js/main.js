/**
 * main.js
 * Script principal para la aplicación DataLayer Validator
 */

// Función para inicializar elementos globales
function initializeUI() {
    // Inicializar tooltips de Bootstrap
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Inicializar popovers de Bootstrap
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));

    // Manejar mensajes flash
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert.alert-dismissible:not(.no-auto-close)');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            setTimeout(() => bsAlert.close(), 5000);
        });
    }, 3000);

    // Manejar botones de copiar al portapapeles
    document.querySelectorAll('.copy-button').forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const textToCopy = document.getElementById(targetId).textContent;

            navigator.clipboard.writeText(textToCopy).then(() => {
                // Cambiar texto del botón temporalmente
                const originalText = this.textContent;
                this.textContent = '¡Copiado!';
                setTimeout(() => {
                    this.textContent = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Error al copiar al portapapeles:', err);
            });
        });
    });

    // Manejar campos de archivo
    document.querySelectorAll('.custom-file-input').forEach(fileInput => {
        fileInput.addEventListener('change', function() {
            const fileName = this.files[0]?.name;
            const label = this.nextElementSibling;

            if (fileName) {
                label.textContent = fileName;
            } else {
                label.textContent = 'Seleccionar archivo';
            }
        });
    });
}

// Función para colorear la sintaxis JSON
function formatJsonSyntax(jsonString) {
    if (!jsonString) return '';

    // Escape HTML characters
    jsonString = jsonString.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Add colors for different parts
    return jsonString.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
        let cls = 'json-number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'json-key';
            } else {
                cls = 'json-string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'json-boolean';
        } else if (/null/.test(match)) {
            cls = 'json-null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}

// Función para generar un ID único
function generateUniqueId(prefix = 'id') {
    return `${prefix}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

// Función para formatear fecha y hora
function formatDateTime(dateString) {
    if (!dateString) return '';

    const date = new Date(dateString);

    return date.toLocaleString('es-ES', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Función para mostrar una notificación
function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');

    if (!container) {
        console.warn('Contenedor de notificaciones no encontrado');
        return;
    }

    const id = generateUniqueId('notification');
    const html = `
        <div id="${id}" class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', html);

    const toastElement = document.getElementById(id);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 5000
    });

    toast.show();

    // Eliminar después de ocultarse
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

// Función para analizar parámetros de URL
function getUrlParameter(name) {
    name = name.replace(/[\[]/, '\\[').replace(/[\]]/, '\\]');
    const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
    const results = regex.exec(location.search);
    return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
}

// Función para navegar a una URL con parámetros
function navigateWithParams(baseUrl, params) {
    const url = new URL(baseUrl, window.location.origin);

    Object.keys(params).forEach(key => {
        if (params[key]) {
            url.searchParams.set(key, params[key]);
        }
    });

    window.location.href = url.toString();
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    initializeUI();

    // Detectar la página actual
    const currentPath = window.location.pathname;

    // Inicializar componentes específicos según la página
    if (currentPath.includes('/session/')) {
        // La inicialización del WebSocket se hace en session_websocket.js
        console.log('Página de sesión detectada');
    } else if (currentPath.includes('/report/')) {
        console.log('Página de reporte detectada');
        // Código específico para la página de reporte
    } else if (currentPath === '/' || currentPath === '/home/') {
        console.log('Página de inicio detectada');
        // Código específico para la página de inicio
    }

    // Manejar formularios de búsqueda
    const searchForms = document.querySelectorAll('.search-form');
    searchForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            // Evitar envío de búsquedas vacías
            const searchInput = this.querySelector('input[name="search"]');
            if (searchInput && !searchInput.value.trim()) {
                event.preventDefault();
            }
        });
    });
});

// Exportar funciones útiles para otros scripts
window.dataLayerValidator = {
    formatJsonSyntax,
    formatDateTime,
    showNotification,
    getUrlParameter,
    navigateWithParams,
    generateUniqueId
};
