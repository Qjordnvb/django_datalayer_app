/**
 * session_ui.js
 * Maneja la interfaz de usuario para la página de sesión de validación
 */

class SessionUI {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.webSocket = null;

        // Elementos DOM principales
        this.screenshotElement = document.getElementById('browser-screenshot');
        this.modalScreenshotElement = document.getElementById('modal-browser-screenshot');
        this.datalayerContainer = document.getElementById('datalayer-container');
        this.totalDatalayers = document.getElementById('total-datalayers');
        this.validDatalayers = document.getElementById('valid-datalayers');
        this.invalidDatalayers = document.getElementById('invalid-datalayers');
        this.validProgress = document.getElementById('valid-progress');
        this.invalidProgress = document.getElementById('invalid-progress');
        this.validationMessage = document.getElementById('validation-message');

        // Inicializar
        this.initialize();
    }

    /**
     * Inicializa la interfaz de usuario y conecta el WebSocket
     */
    initialize() {
        // Configurar estados iniciales
        this.setLoading(true);

        // Inicializar WebSocket (asume que SessionWebSocket ya está cargado)
        this.webSocket = new SessionWebSocket(this.sessionId);

        // Configurar observadores para eventos WebSocket
        this.setupWebSocketObservers();

        // Iniciar la conexión
        this.webSocket.connect();

        // Configurar eventos de la interfaz
        this.setupUIEvents();
    }

    /**
     * Configura observadores para eventos del WebSocket
     */
    setupWebSocketObservers() {
        this.webSocket.subscribe('screenshot', this.handleScreenshot.bind(this));
        this.webSocket.subscribe('datalayer', this.handleDataLayer.bind(this));
        this.webSocket.subscribe('url_changed', this.handleUrlChanged.bind(this));
        this.webSocket.subscribe('validation', this.handleValidation.bind(this));
        this.webSocket.subscribe('error', this.handleError.bind(this));
        this.webSocket.subscribe('connection', this.handleConnection.bind(this));
        this.webSocket.subscribe('report', this.handleReport.bind(this));
    }

    /**
     * Configura los eventos de la interfaz de usuario
     */
    setupUIEvents() {
        // Drag & Drop para archivos JSON (mejora futura)
        const dropZone = document.querySelector('.browser-container');
        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('drag-over');
            });

            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('drag-over');
            });

            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('drag-over');

                // Procesamiento de archivos arrastrados (implementación futura)
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    console.log('Archivo recibido:', files[0].name);
                    // Aquí se procesaría el archivo
                }
            });
        }

        // Búsqueda de DataLayers
        const searchInput = document.getElementById('search-datalayer');
        if (searchInput) {
            searchInput.addEventListener('input', this.handleSearch.bind(this));
        }

        // Cambio de vista (lista/detalle/comparación)
        const viewSwitchers = document.querySelectorAll('[data-view]');
        viewSwitchers.forEach(element => {
            element.addEventListener('click', (e) => {
                e.preventDefault();
                const view = element.dataset.view;
                this.switchView(view);
            });
        });
    }

    /**
     * Maneja la llegada de una captura de pantalla
     */
    handleScreenshot(data) {
        this.setLoading(false);

        if (data.image_url) {
            // Añadir parámetro de timestamp para evitar caché
            const imgUrl = `${data.image_url}?t=${Date.now()}`;

            // Actualizar imágenes
            if (this.screenshotElement) {
                this.screenshotElement.src = imgUrl;
            }

            if (this.modalScreenshotElement) {
                this.modalScreenshotElement.src = imgUrl;
            }
        }
    }

    /**
     * Maneja la captura de un DataLayer
     */
    handleDataLayer(data) {
        // Si es el primer DataLayer capturado, limpiar el contenedor
        if (this.datalayerContainer.querySelector('.datalayer-placeholder')) {
            this.datalayerContainer.innerHTML = '';
        }

        // Crear elemento para el DataLayer
        const datalayerElement = this.createDataLayerElement(data);

        // Agregar al contenedor (al principio para que aparezca arriba)
        this.datalayerContainer.insertBefore(datalayerElement, this.datalayerContainer.firstChild);

        // Animar aparición
        setTimeout(() => {
            datalayerElement.classList.add('show');
        }, 10);

        // Mostrar notificación
        const status = data.valid === true ? 'válido' : (data.valid === false ? 'inválido' : 'sin validar');
        const type = data.valid === true ? 'success' : (data.valid === false ? 'danger' : 'warning');

        window.dataLayerValidator.showNotification(
            `DataLayer capturado: ${data.event || 'Push'} (${status})`,
            type
        );
    }

    /**
     * Crea un elemento HTML para mostrar un DataLayer
     */
    createDataLayerElement(data) {
        const id = window.dataLayerValidator.generateUniqueId('datalayer');
        const jsonId = `json-${id}`;

        // Determinar clase según estado de validación
        let statusClass = 'warning';
        let statusBadge = '<span class="badge bg-warning">Sin validar</span>';

        if (data.valid === true) {
            statusClass = 'valid';
            statusBadge = '<span class="badge bg-success">Válido</span>';
        } else if (data.valid === false) {
            statusClass = 'invalid';
            statusBadge = '<span class="badge bg-danger">Inválido</span>';
        }

        // Crear elemento
        const div = document.createElement('div');
        div.className = `datalayer-event ${statusClass}`;
        div.id = id;
        div.style.opacity = '0';
        div.classList.add('fade-in');

        // Contenido HTML
        div.innerHTML = `
            <div class="datalayer-event-header">
                <div>
                    <h6 class="mb-0">${data.event || 'DataLayer Push'}</h6>
                    <div class="event-meta">
                        <span class="event-meta-item">
                            <i class="far fa-clock"></i> ${window.dataLayerValidator.formatDateTime(data.timestamp)}
                        </span>
                    </div>
                </div>
                ${statusBadge}
            </div>
            <div class="datalayer-event-content">
                <div class="json-viewer-container">
                    <div class="json-viewer">
                        <pre id="${jsonId}">${window.dataLayerValidator.formatJsonSyntax(JSON.stringify(data.data, null, 2))}</pre>
                    </div>
                    <button class="copy-button" data-target="${jsonId}">
                        <i class="far fa-copy"></i> Copiar
                    </button>
                </div>

                ${data.errors && data.errors.length > 0 ? `
                <div class="validation-info">
                    <h6><i class="fas fa-exclamation-triangle text-danger"></i> Errores de validación:</h6>
                    <ul class="validation-errors">
                        ${data.errors.map(error => `<li>${error}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}
            </div>
        `;

        // Configurar botón de copiar
        const copyButton = div.querySelector('.copy-button');
        copyButton.addEventListener('click', () => {
            const jsonText = JSON.stringify(data.data, null, 2);
            navigator.clipboard.writeText(jsonText).then(() => {
                copyButton.innerHTML = '<i class="fas fa-check"></i> Copiado';
                setTimeout(() => {
                    copyButton.innerHTML = '<i class="far fa-copy"></i> Copiar';
                }, 2000);
            });
        });

        return div;
    }

    /**
     * Maneja el cambio de URL
     */
    handleUrlChanged(data) {
        if (data.url) {
            const urlElements = document.querySelectorAll('#current-url, #modal-current-url');
            urlElements.forEach(element => {
                if (element) element.textContent = data.url;
            });
        }
    }

    /**
     * Maneja resultados de validación
     */
    handleValidation(data) {
        if (this.validationMessage && data.message) {
            this.validationMessage.textContent = data.message;
        }

        // Actualizar estadísticas si están disponibles
        if (data.valid_count !== undefined && data.invalid_count !== undefined) {
            this.updateValidationStats(data.valid_count, data.invalid_count);
        }
    }

    /**
     * Maneja errores del WebSocket
     */
    handleError(data) {
        console.error('Error WebSocket:', data.message);
        window.dataLayerValidator.showNotification(data.message, 'danger');
    }

    /**
     * Maneja eventos de conexión
     */
    handleConnection(data) {
        if (data.connected) {
            console.log('WebSocket conectado');
        } else {
            console.log('WebSocket desconectado');
            this.setLoading(true);
        }
    }

    /**
     * Maneja generación de reportes
     */
    handleReport(data) {
        if (data.status === 'generated' && data.report_url) {
            window.dataLayerValidator.showNotification(
                `Reporte generado correctamente`,
                'success'
            );

            // Redirigir al reporte después de un breve retraso
            setTimeout(() => {
                window.location.href = data.report_url;
            }, 1500);
        }
    }

    /**
     * Actualiza las estadísticas de validación
     */
    updateValidationStats(validCount, invalidCount) {
        if (!this.totalDatalayers || !this.validDatalayers || !this.invalidDatalayers) {
            return;
        }

        const total = validCount + invalidCount;

        // Actualizar contadores
        this.totalDatalayers.textContent = total;
        this.validDatalayers.textContent = validCount;
        this.invalidDatalayers.textContent = invalidCount;

        // Calcular porcentajes
        let validPercent = 0;
        let invalidPercent = 0;

        if (total > 0) {
            validPercent = Math.round((validCount / total) * 100);
            invalidPercent = Math.round((invalidCount / total) * 100);
        }

        // Actualizar barras de progreso
        if (this.validProgress && this.invalidProgress) {
            this.validProgress.style.width = `${validPercent}%`;
            this.validProgress.setAttribute('aria-valuenow', validPercent);
            this.validProgress.textContent = `${validPercent}%`;

            this.invalidProgress.style.width = `${invalidPercent}%`;
            this.invalidProgress.setAttribute('aria-valuenow', invalidPercent);
            this.invalidProgress.textContent = `${invalidPercent}%`;
        }

        // Actualizar mensaje
        if (this.validationMessage) {
            if (total === 0) {
                this.validationMessage.textContent = 'La validación comenzará cuando se capturen DataLayers.';
            } else if (validPercent === 100) {
                this.validationMessage.textContent = '¡Todos los DataLayers capturados son válidos!';
            } else if (invalidPercent === 100) {
                this.validationMessage.textContent = 'Todos los DataLayers capturados tienen errores.';
            } else {
                this.validationMessage.textContent = `${validPercent}% de los DataLayers son válidos, ${invalidPercent}% tienen errores.`;
            }
        }
    }

    /**
     * Muestra u oculta el indicador de carga
     */
    setLoading(isLoading) {
        const loadingIndicators = document.querySelectorAll('#loading-indicator, #modal-loading-indicator');
        loadingIndicators.forEach(indicator => {
            if (indicator) {
                indicator.style.display = isLoading ? 'flex' : 'none';
            }
        });
    }

    /**
     * Maneja la búsqueda de DataLayers
     */
    handleSearch(e) {
        const searchTerm = e.target.value.toLowerCase().trim();
        const dataLayerElements = this.datalayerContainer.querySelectorAll('.datalayer-event');

        dataLayerElements.forEach(element => {
            const jsonText = element.querySelector('.json-viewer pre').textContent.toLowerCase();
            const eventName = element.querySelector('.datalayer-event-header h6').textContent.toLowerCase();

            const isMatch = jsonText.includes(searchTerm) || eventName.includes(searchTerm);
            element.style.display = isMatch ? 'block' : 'none';

            // Si hay coincidencia y término de búsqueda, resaltar
            if (isMatch && searchTerm) {
                this.highlightSearchTerm(element, searchTerm);
            } else {
                this.removeHighlights(element);
            }
        });

        // Mostrar mensaje si no hay resultados
        let noResultsMsg = this.datalayerContainer.querySelector('.no-results-message');
        const hasResults = Array.from(dataLayerElements).some(el => el.style.display === 'block');

        if (!hasResults && searchTerm) {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.className = 'no-results-message text-center p-4 text-muted';
                noResultsMsg.innerHTML = '<i class="fas fa-search mb-3"></i><p>No se encontraron resultados para esta búsqueda.</p>';
                this.datalayerContainer.appendChild(noResultsMsg);
            }
        } else if (noResultsMsg) {
            noResultsMsg.remove();
        }
    }

    /**
     * Resalta términos de búsqueda en un elemento
     */
    highlightSearchTerm(element, term) {
        // Primero restaurar el contenido original
        this.removeHighlights(element);

        // Luego resaltar en el nuevo contenido
        const jsonViewerPre = element.querySelector('.json-viewer pre');
        if (!jsonViewerPre) return;

        const originalHtml = jsonViewerPre.innerHTML;

        // Crear RegExp para reemplazar el término manteniendo el formato HTML
        const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\                this.validationMessage.textContent = `${validPerc');
        const regex = new RegExp(`(${escapedTerm})`, 'gi');

        // Reemplazar solo el texto, preservando las etiquetas HTML
        const newHtml = this.replaceTextWithinHTML(originalHtml, regex, (match) => {
            return `<span class="highlight-search">${match}</span>`;
        });

        jsonViewerPre.innerHTML = newHtml;
    }

    /**
     * Reemplaza texto dentro de HTML preservando las etiquetas
     */
    replaceTextWithinHTML(html, regex, replacementFn) {
        let parts = html.split(/(<[^>]+>)/);
        for (let i = 0; i < parts.length; i++) {
            // Solo reemplazar en partes que no son etiquetas HTML
            if (!parts[i].startsWith('<') && !parts[i].endsWith('>')) {
                parts[i] = parts[i].replace(regex, replacementFn);
            }
        }
        return parts.join('');
    }

    /**
     * Elimina resaltados de búsqueda
     */
    removeHighlights(element) {
        const jsonViewerPre = element.querySelector('.json-viewer pre');
        if (!jsonViewerPre) return;

        // Guardar el contenido sin etiquetas de resaltado
        const originalContent = jsonViewerPre.innerHTML;
        const cleanContent = originalContent.replace(/<span class="highlight-search">([^<]+)<\/span>/g, '$1');

        jsonViewerPre.innerHTML = cleanContent;
    }

    /**
     * Cambia entre diferentes vistas
     */
    switchView(viewType) {
        const viewElements = document.querySelectorAll('[data-view-content]');
        const tabElements = document.querySelectorAll('[data-view]');

        // Activar la pestaña seleccionada
        tabElements.forEach(tab => {
            if (tab.dataset.view === viewType) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Mostrar el contenido correspondiente
        viewElements.forEach(element => {
            if (element.dataset.viewContent === viewType) {
                element.classList.remove('d-none');
            } else {
                element.classList.add('d-none');
            }
        });
    }

    /**
     * Agrupa los DataLayers por tipo de evento
     */
    groupDataLayersByEvent() {
        const dataLayerElements = this.datalayerContainer.querySelectorAll('.datalayer-event');
        const groups = {};

        dataLayerElements.forEach(element => {
            const eventName = element.querySelector('.datalayer-event-header h6').textContent;

            if (!groups[eventName]) {
                groups[eventName] = [];
            }

            groups[eventName].push(element);
        });

        return groups;
    }
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    // Obtener el ID de la sesión
    const sessionId = document.body.getAttribute('data-session-id');

    if (sessionId) {
        // Inicializar la interfaz de usuario
        window.sessionUI = new SessionUI(sessionId);
    }
});
