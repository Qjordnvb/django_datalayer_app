/**
 * session_websocket.js
 * Gestiona la comunicación por WebSockets para la página de sesión de validación
 * de DataLayer Validator
 */

class SessionWebSocket {
    constructor(sessionId) {
        // --- Verificaciones iniciales ---
        if (!sessionId) {
            throw new Error("SessionWebSocket: Se requiere un ID de sesión.");
        }
        console.log(`SessionWebSocket: Creando instancia para sesión ${sessionId}`);
        this.sessionId = sessionId;

        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5; // Intentos máximos de reconexión
        this.reconnectInterval = 3000; // Intervalo en ms (3 segundos)
        this.observers = {}; // Para posible patrón observador

        // --- Obtener referencias a elementos DOM (con verificación) ---
        this.screenshotElement = document.getElementById('browser-screenshot');
        this.modalScreenshotElement = document.getElementById('modal-browser-screenshot');
        this.loadingIndicator = document.getElementById('loading-indicator');
        this.modalLoadingIndicator = document.getElementById('modal-loading-indicator');
        this.currentUrlElement = document.getElementById('current-url');
        this.modalCurrentUrlElement = document.getElementById('modal-current-url'); // ID del campo URL en modal
        this.screenshotCountElement = document.getElementById('screenshot-count');
        this.datalayerCountElement = document.getElementById('datalayer-count');
        this.datalayerBadgeElement = document.getElementById('datalayer-badge');
        this.datalayerContainer = document.getElementById('datalayer-container');

        // Elementos de estadísticas
        this.totalDatalayers = document.getElementById('total-datalayers');
        this.validDatalayers = document.getElementById('valid-datalayers');
        this.invalidDatalayers = document.getElementById('invalid-datalayers');
        this.validProgress = document.getElementById('valid-progress');
        this.invalidProgress = document.getElementById('invalid-progress');
        this.validationMessage = document.getElementById('validation-message');

        // Template para eventos
        this.datalayerTemplate = document.getElementById('datalayer-event-template');

        // Verificar elementos esenciales
        if (!this.screenshotElement || !this.modalScreenshotElement || !this.datalayerContainer || !this.datalayerTemplate) {
             console.error("SessionWebSocket: Faltan elementos DOM esenciales (screenshot, datalayer container o template). La UI podría no funcionar correctamente.");
        }

        // Contadores internos
        this.screenshotCount = 0;
        this.datalayerCount = 0;
        this.validCount = 0;
        this.invalidCount = 0;

        console.log("SessionWebSocket: Instancia creada.");
    }

    /**
     * Conecta al WebSocket y configura los manejadores de eventos
     */
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/session/${this.sessionId}/`;
        console.log(`SessionWebSocket: Intentando conectar a ${wsUrl}`);

        // Evitar conexiones duplicadas
        if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
            console.warn("SessionWebSocket: Intento de conexión mientras ya existe una conexión activa o conectando.");
            return;
        }

        try {
            this.socket = new WebSocket(wsUrl);
        } catch (error) {
             console.error("SessionWebSocket: Error al crear instancia de WebSocket.", error);
             // Podríamos intentar reconectar aquí o mostrar un error fatal
             this.handleError({ message: `No se pudo crear WebSocket: ${error.message}` });
             return;
        }

        // Asignar manejadores
        this.socket.onopen = this.handleOpen.bind(this);
        this.socket.onclose = this.handleClose.bind(this);
        this.socket.onerror = this.handleError.bind(this); // Maneja errores de conexión
        this.socket.onmessage = this.handleMessage.bind(this);

        this.showLoading(); // Mostrar carga mientras conecta
    }

    /**
     * Maneja el evento de apertura de conexión WebSocket
     */
    handleOpen(event) {
        console.log('SessionWebSocket: Conectado.');
        this.connected = true;
        this.reconnectAttempts = 0; // Resetear intentos al conectar
        this.hideLoading();

        // Limpiar alerta de reconexión si existe
        const reconnectAlert = document.getElementById('ws-reconnect-alert');
        if (reconnectAlert) reconnectAlert.remove();

        // Enviar mensaje 'init' para que el backend inicie Playwright y envíe estado
        this.sendMessage({
            action: 'init',
            sessionId: this.sessionId
        });

        this.notifyObservers('connection', { connected: true });
        // Usar la función global de notificaciones si existe
        if (window.dataLayerValidator && window.dataLayerValidator.showNotification) {
            window.dataLayerValidator.showNotification('Conectado a la sesión interactiva.', 'success');
        }
    }

    /**
     * Maneja el evento de cierre de conexión WebSocket
     */
    handleClose(event) {
        this.connected = false;
        console.log(`SessionWebSocket: Desconectado. Código: ${event.code}, Razón: ${event.reason || 'N/A'}, Limpio: ${event.wasClean}`);
        this.hideLoading();

        // Intentar reconexión solo si el cierre fue inesperado (código 1006 es común para fallos)
        if (!event.wasClean || event.code === 1006) {
             console.log("SessionWebSocket: Cierre inesperado, intentando reconexión...");
            this.attemptReconnect();
        } else {
             console.log("SessionWebSocket: Cierre normal o intencional, no se reconectará.");
             if (event.code === 1000 && window.dataLayerValidator) { // 1000 es cierre normal
                 window.dataLayerValidator.showNotification('Sesión finalizada.', 'info');
             }
             // Si el cierre fue por otra razón (ej. error del servidor 1011), mostrar mensaje
             else if (event.code !== 1001 && window.dataLayerValidator) { // 1001 es 'Going Away' (ej. recarga de página)
                  window.dataLayerValidator.showNotification(`Desconectado: ${event.reason || event.code}`, 'warning');
             }
             // Deshabilitar interacción si la sesión terminó
             if(event.code === 1000) this.disableInteraction();
        }

        this.notifyObservers('connection', { connected: false, code: event.code });
    }

    /**
     * Maneja errores de conexión WebSocket
     * Nota: onerror usualmente es seguido por onclose.
     */
    handleError(error) {
        // 'error' puede ser un objeto Event o un objeto Error simple
        console.error('SessionWebSocket: Error de WebSocket:', error);
        this.hideLoading();
        // La lógica de reconexión se maneja en handleClose tras un error.
        // Solo notificamos aquí si la función global existe.
        if (window.dataLayerValidator && window.dataLayerValidator.showNotification) {
            // No mostramos el mensaje de reconexión aquí para evitar duplicados con handleClose
             window.dataLayerValidator.showNotification('Error de conexión WebSocket.', 'danger');
        }
    }

    /**
     * Procesa mensajes JSON recibidos del servidor backend
     */
    handleMessage(event) {
        console.debug("SessionWebSocket: Mensaje recibido:", event.data);
        try {
            const data = JSON.parse(event.data);

            if (!data.action) {
                console.error('SessionWebSocket: Mensaje recibido del backend sin acción definida:', data);
                return;
            }

            // Llamar dinámicamente al método manejador (ej. handleScreenshot)
            const handlerMethodName = `handle${data.action.charAt(0).toUpperCase() + data.action.slice(1)}`;
            if (typeof this[handlerMethodName] === 'function') {
                this[handlerMethodName](data);
            } else {
                console.warn('SessionWebSocket: Acción desconocida recibida del backend:', data.action, data);
            }

            // Notificar a los observadores genéricos (si se implementa)
            this.notifyObservers(data.action, data);

        } catch (error) {
            console.error('SessionWebSocket: Error al parsear o procesar mensaje JSON del backend:', error, "Mensaje original:", event.data);
            if (window.dataLayerValidator && window.dataLayerValidator.showNotification) {
                 window.dataLayerValidator.showNotification('Error al procesar respuesta del servidor.', 'danger');
            }
        }
    }

    // --- MANEJADORES DE MENSAJES ESPECÍFICOS ---

    handleScreenshot(data) {
        this.hideLoading(); // Ocultar indicador si estaba visible
        if (data.image_url && this.screenshotElement && this.modalScreenshotElement) {
            const timestampedUrl = `${data.image_url}?t=${Date.now()}`; // Evitar caché
            this.screenshotElement.src = timestampedUrl;
            this.modalScreenshotElement.src = timestampedUrl; // Actualizar también en el modal
            this.screenshotCount++;
            if(this.screenshotCountElement) this.screenshotCountElement.textContent = this.screenshotCount;
            console.debug("SessionWebSocket: Screenshot actualizado.");
        } else {
            console.warn("SessionWebSocket: Mensaje 'screenshot' recibido sin URL o elementos img no encontrados.");
        }
    }

    handleDatalayer(data) {
        this.datalayerCount++;
        if(this.datalayerCountElement) this.datalayerCountElement.textContent = this.datalayerCount;
        if(this.datalayerBadgeElement) this.datalayerBadgeElement.textContent = this.datalayerCount;

        // Limpiar mensaje placeholder si es el primer datalayer
        if (this.datalayerCount === 1 && this.datalayerContainer) {
             const placeholder = this.datalayerContainer.querySelector('.text-muted'); // Busca el párrafo placeholder
             if(placeholder && placeholder.parentElement.classList.contains('text-center')) {
                 placeholder.parentElement.remove();
             }
        }

        if (this.datalayerContainer && this.datalayerTemplate) {
             try {
                const templateContent = this.datalayerTemplate.content.cloneNode(true);
                const datalayerEventDiv = templateContent.querySelector('.datalayer-event');
                const eventNameEl = templateContent.querySelector('.event-name');
                const eventTimeEl = templateContent.querySelector('.event-time');
                const badgeEl = templateContent.querySelector('.validation-badge');
                const dataCodeEl = templateContent.querySelector('.event-data'); // El <code> dentro de <pre>
                const validationInfoEl = templateContent.querySelector('.validation-info');
                const errorsListEl = templateContent.querySelector('.validation-errors');

                // Estado de validación
                let statusClass = 'warning';
                let badgeText = 'Pendiente';
                let badgeClass = 'bg-secondary'; // Usar secondary para pendiente
                if (data.valid === true) {
                    statusClass = 'valid'; badgeText = 'VÁLIDO'; badgeClass = 'bg-success'; this.validCount++;
                } else if (data.valid === false) {
                    statusClass = 'invalid'; badgeText = 'INVÁLIDO'; badgeClass = 'bg-danger'; this.invalidCount++;
                }
                datalayerEventDiv.classList.add(statusClass);
                badgeEl.textContent = badgeText;
                badgeEl.className = `badge validation-badge ${badgeClass}`;

                // Datos básicos
                eventNameEl.textContent = data.event || 'dataLayer Push'; // Nombre del evento o push genérico
                eventTimeEl.textContent = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

                // Mostrar JSON con formato
                const jsonDataString = JSON.stringify(data.data, null, 2);
                if (window.dataLayerValidator && typeof window.dataLayerValidator.formatJsonSyntax === 'function') {
                    dataCodeEl.innerHTML = window.dataLayerValidator.formatJsonSyntax(jsonDataString);
                } else {
                    dataCodeEl.textContent = jsonDataString; // Fallback sin formato
                }

                // Mostrar errores si existen
                if (data.errors && data.errors.length > 0 && validationInfoEl && errorsListEl) {
                    validationInfoEl.style.display = 'block'; // Mostrar sección de errores
                    errorsListEl.innerHTML = ''; // Limpiar
                    data.errors.forEach(error => {
                        const errorItem = document.createElement('li');
                        // Sanitizar HTML si 'error' puede contenerlo
                        errorItem.innerHTML = `<i class="fas fa-times-circle text-danger me-1"></i> `;
                        errorItem.appendChild(document.createTextNode(error)); // Más seguro
                        errorsListEl.appendChild(errorItem);
                    });
                } else if (validationInfoEl) {
                    validationInfoEl.style.display = 'none'; // Ocultar si no hay errores
                }

                // Agregar al contenedor (al principio para ver los más recientes primero)
                this.datalayerContainer.insertBefore(templateContent, this.datalayerContainer.firstChild);
                this.updateValidationStats();
                console.debug("SessionWebSocket: DataLayer añadido a la UI.");

             } catch(e) {
                 console.error("SessionWebSocket: Error al crear/añadir elemento datalayer desde template:", e);
             }
        } else {
             console.warn("SessionWebSocket: No se pudo añadir datalayer, el contenedor o el template no fueron encontrados en el DOM.");
        }
    }

    handleUrlChanged(data) {
        if (data.url) {
            const newUrl = data.url;
            if(this.currentUrlElement) this.currentUrlElement.textContent = newUrl;
            const modalUrlElement = document.getElementById('modal-current-url'); // ID del campo en modal
            if(modalUrlElement) modalUrlElement.textContent = newUrl;
            // Actualizar también el título del modal de pantalla completa si existe
             const modalTitleUrlElement = document.getElementById('fullscreenModalLabel');
             if(modalTitleUrlElement) {
                 // Preservar el icono
                 const icon = modalTitleUrlElement.querySelector('i');
                 modalTitleUrlElement.textContent = ''; // Limpiar
                 if(icon) modalTitleUrlElement.appendChild(icon);
                 modalTitleUrlElement.appendChild(document.createTextNode(newUrl)); // Añadir nueva URL
             }
             console.debug(`SessionWebSocket: URL actualizada a ${newUrl}`);
        }
    }

    handleStatus(data) {
        console.debug("SessionWebSocket: Mensaje de estado ('status') recibido:", data);
        // Actualizar contadores
        if (data.screenshot_count !== undefined && this.screenshotCountElement) {
            this.screenshotCount = data.screenshot_count;
            this.screenshotCountElement.textContent = this.screenshotCount;
        }
        if (data.datalayer_count !== undefined && this.datalayerCountElement && this.datalayerBadgeElement) {
            this.datalayerCount = data.datalayer_count;
            this.datalayerCountElement.textContent = this.datalayerCount;
            this.datalayerBadgeElement.textContent = this.datalayerCount;
        }
        // Actualizar URL
        if (data.current_url) {
            this.handleUrlChanged(data);
        }
        // Actualizar estadísticas de validación
        if (data.valid_count !== undefined && data.invalid_count !== undefined) {
            this.validCount = data.valid_count;
            this.invalidCount = data.invalid_count;
            this.updateValidationStats();
        }
         // Actualizar badge de estado de la sesión
         const statusBadge = document.getElementById('session-status-badge');
         if(statusBadge && data.session_status) {
             let badgeClass = 'bg-secondary';
             let statusText = data.session_status; // Texto por defecto

             switch(data.session_status) {
                 case 'active': badgeClass = 'bg-success'; statusText = 'Activa'; break;
                 case 'completed': badgeClass = 'bg-primary'; statusText = 'Completada'; break;
                 case 'error': badgeClass = 'bg-danger'; statusText = 'Error'; break;
                 case 'pending': badgeClass = 'bg-warning text-dark'; statusText = 'Pendiente'; break;
             }
             statusBadge.className = `badge ${badgeClass}`;
             statusBadge.textContent = statusText;
         }
    }

    handleValidation(data) {
        console.debug("SessionWebSocket: Mensaje de validación ('validation') recibido:", data);
        if (data.message && this.validationMessage) {
            this.validationMessage.textContent = data.message;
        }
        if (data.valid_count !== undefined && data.invalid_count !== undefined) {
            this.validCount = data.valid_count;
            this.invalidCount = data.invalid_count;
            this.updateValidationStats();
        }
    }

     handleSession(data) {
         console.debug("SessionWebSocket: Mensaje de sesión ('session') recibido:", data);
         if(data.status === 'completed') {
              if (window.dataLayerValidator && window.dataLayerValidator.showNotification) {
                 window.dataLayerValidator.showNotification(data.message || 'Sesión finalizada.', 'info');
              }
              this.disableInteraction(); // Deshabilitar controles
              // Actualizar badge de estado
              this.handleStatus({session_status: 'completed'});
         }
     }

     handleReport(data) {
          console.debug("SessionWebSocket: Mensaje de reporte ('report') recibido:", data);
          if(data.status === 'generated' && data.report_url) {
              if (window.dataLayerValidator && window.dataLayerValidator.showNotification) {
                 window.dataLayerValidator.showNotification(data.message || 'Reporte generado.', 'success');
              }
               // Opcional: Ofrecer link o abrir en nueva pestaña
               // const reportLink = document.getElementById('view-report-link'); // Suponiendo que existe tal elemento
               // if(reportLink) { reportLink.href = data.report_url; reportLink.style.display = 'block'; }
          } else if (data.status === 'error') {
              this.handleErrorMessage(data); // Usa el manejador de errores genérico
          }
     }

    handleErrorMessage(data) { // Renombrado de handleerror a handleErrorMessage
        const message = data.message || 'Error desconocido del servidor.';
        console.error('SessionWebSocket: Error recibido del servidor:', message);
        if (window.dataLayerValidator && window.dataLayerValidator.showNotification) {
            window.dataLayerValidator.showNotification(`Error: ${message}`, 'danger');
        }
        this.hideLoading();
    }

    // --- FUNCIONES AUXILIARES UI ---

    updateValidationStats() {
        const total = this.validCount + this.invalidCount;

        if(this.totalDatalayers) this.totalDatalayers.textContent = total;
        if(this.validDatalayers) this.validDatalayers.textContent = this.validCount;
        if(this.invalidDatalayers) this.invalidDatalayers.textContent = this.invalidCount;

        let validPercent = 0;
        let invalidPercent = 0;
        if (total > 0) {
            validPercent = Math.round((this.validCount / total) * 100);
            // Asegurar que la suma sea 100% en la barra
            invalidPercent = 100 - validPercent;
        }

        if (this.validProgress) {
            this.validProgress.style.width = `${validPercent}%`;
            this.validProgress.setAttribute('aria-valuenow', validPercent);
            this.validProgress.textContent = total > 0 ? `${validPercent}%` : ''; // No mostrar 0%
        }
        if (this.invalidProgress) {
            this.invalidProgress.style.width = `${invalidPercent}%`;
            this.invalidProgress.setAttribute('aria-valuenow', invalidPercent);
            this.invalidProgress.textContent = invalidPercent > 0 ? `${invalidPercent}%` : '';
        }

        if (this.validationMessage) {
            if (total === 0) {
                this.validationMessage.textContent = 'Esperando DataLayers para validar.';
            } else {
                this.validationMessage.textContent = `Validación: ${validPercent}% éxito (${this.validCount}/${total}).`;
            }
        }
         console.debug(`SessionWebSocket: Estadísticas actualizadas - V:${this.validCount}, I:${this.invalidCount}, T:${total}`);
    }

    attemptReconnect() {
        // No intentar reconectar si el socket está abriendo, abierto o si ya se alcanzó el límite
        if (!this.socket || this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING || this.reconnectAttempts >= this.maxReconnectAttempts) {
             if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                  console.warn('SessionWebSocket: Número máximo de intentos de reconexión alcanzado.');
                  if (window.dataLayerValidator) {
                     window.dataLayerValidator.showNotification('No se pudo reconectar. Por favor, recarga la página.', 'danger', 10000); // Mensaje más duradero
                  }
                  this.hideLoading();
                  // Podríamos deshabilitar interacción aquí también si falla la reconexión
                  // this.disableInteraction();
             }
            return;
        }

        this.reconnectAttempts++;
        console.log(`SessionWebSocket: Intentando reconexión (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

        // Mostrar mensaje visual de intento de reconexión
        let reconnectAlert = document.getElementById('ws-reconnect-alert');
        if (!reconnectAlert) {
            reconnectAlert = document.createElement('div');
            reconnectAlert.id = 'ws-reconnect-alert';
            reconnectAlert.className = 'alert alert-warning fixed-top text-center mb-0 py-1'; // Más discreto
            reconnectAlert.style.zIndex = '1051'; // Encima de notificaciones
            reconnectAlert.role = 'alert';
             const mainContainer = document.querySelector('main.container');
              if(mainContainer) {
                 mainContainer.prepend(reconnectAlert);
             } else {
                  document.body.prepend(reconnectAlert);
             }
        }
        reconnectAlert.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>Conexión perdida. Intentando reconectar (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`;


        setTimeout(() => {
            // Solo intentar conectar si aún no estamos conectados
            if (!this.connected && this.socket && this.socket.readyState !== WebSocket.OPEN) {
                console.log(`SessionWebSocket: Ejecutando intento de conexión ${this.reconnectAttempts}`);
                this.connect(); // Llama a connect, que creará un nuevo socket
            } else {
                 // Si ya se conectó (quizás manualmente o por otro evento), quitar la alerta
                 if (reconnectAlert) reconnectAlert.remove();
            }
        }, this.reconnectInterval);
    }

    sendMessage(message) {
        if (this.connected && this.socket && this.socket.readyState === WebSocket.OPEN) {
             console.debug('SessionWebSocket: Enviando mensaje:', message);
            this.socket.send(JSON.stringify(message));
        } else {
            console.warn('SessionWebSocket: No se puede enviar mensaje, WebSocket no conectado o no listo. Estado:', this.socket ? this.socket.readyState : 'Socket nulo');
             if (window.dataLayerValidator && window.dataLayerValidator.showNotification) {
                window.dataLayerValidator.showNotification('No se pudo enviar la acción. La conexión está perdida.', 'warning');
            }
        }
    }

    showLoading() {
        if (this.loadingIndicator) this.loadingIndicator.style.display = 'flex';
        if (this.modalLoadingIndicator) this.modalLoadingIndicator.style.display = 'flex';
    }

    hideLoading() {
        if (this.loadingIndicator) this.loadingIndicator.style.display = 'none';
        if (this.modalLoadingIndicator) this.modalLoadingIndicator.style.display = 'none';
    }


    clickElement(selector) {
    if (!selector) {
        if (window.dataLayerValidator) window.dataLayerValidator.showNotification('Selector es requerido.', 'warning');
        return;
    }
    this.showLoading();
    this.sendMessage({ action: 'interaction', command: 'click', selector: selector });
}

typeText(selector, text) {
    if (!selector || text === undefined) {
        if (window.dataLayerValidator) window.dataLayerValidator.showNotification('Selector y texto son requeridos.', 'warning');
        return;
    }
    this.showLoading();
    this.sendMessage({ action: 'interaction', command: 'type', selector: selector, text: text });
}

    disableInteraction() {
        console.log("SessionWebSocket: Deshabilitando interacción...");
        const buttonsToDisable = [
            'back-btn', 'forward-btn', 'reload-btn', 'capture-btn', 'fullscreen-btn',
            'stop-btn', 'goto-btn', 'generate-report-btn', 'capture-datalayer-btn',
            'check-validation-btn', 'take-screenshot-btn', 'confirm-stop-btn',
            'confirm-generate-report-btn', 'modal-back-btn', 'modal-forward-btn',
            'modal-reload-btn', 'modal-capture-btn'
        ];
        buttonsToDisable.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) {
                btn.disabled = true;
                btn.classList.add('disabled'); // Añadir clase visual si es necesario
            }
        });
        const gotoInput = document.getElementById('goto-url');
        if(gotoInput) gotoInput.disabled = true;

        if(this.screenshotElement) this.screenshotElement.style.cursor = 'not-allowed';
        if(this.modalScreenshotElement) this.modalScreenshotElement.style.cursor = 'not-allowed';
         // Podríamos quitar los event listeners de click en las imágenes aquí también
    }

    // --- COMANDOS ENVIADOS AL SERVIDOR ---

    goBack() { this.showLoading(); this.sendMessage({ action: 'navigation', command: 'back' }); }
    goForward() { this.showLoading(); this.sendMessage({ action: 'navigation', command: 'forward' }); }
    reload() { this.showLoading(); this.sendMessage({ action: 'navigation', command: 'reload' }); }
    goToUrl(url) {
        if (!url || !url.trim()) {
            if (window.dataLayerValidator) window.dataLayerValidator.showNotification('Por favor, ingresa una URL válida.', 'warning');
            return;
        }
        let fullUrl = url.trim();
        if (!fullUrl.match(/^https?:\/\//)) {
            fullUrl = 'https://' + fullUrl;
        }
        this.showLoading();
        this.sendMessage({ action: 'navigation', command: 'goto', url: fullUrl });
    }
    captureDataLayer() { this.sendMessage({ action: 'capture', command: 'datalayer' }); }
    takeScreenshot() { this.showLoading(); this.sendMessage({ action: 'capture', command: 'screenshot' }); }
    checkValidation() { this.sendMessage({ action: 'validation', command: 'check' }); }
    stopSession() { console.log("Intentando detener sesión..."); this.sendMessage({ action: 'session', command: 'stop' }); }
    generateReport(options = {}) { console.log("Intentando generar reporte:", options); this.sendMessage({ action: 'report', command: 'generate', options: options }); }
   clickAt(xPercent, yPercent) {
    // Validar porcentajes
    if (typeof xPercent !== 'number' || typeof yPercent !== 'number' || xPercent < 0 || xPercent > 1 || yPercent < 0 || yPercent > 1) {
        console.error("SessionWebSocket: Coordenadas de clic inválidas:", xPercent, yPercent);
        return;
    }
    console.log(`Enviando clic en coordenadas relativas: x=${xPercent.toFixed(3)}, y=${yPercent.toFixed(3)}`);
    this.showLoading();
    this.sendMessage({ action: 'interaction', command: 'click', x: xPercent, y: yPercent });
}

    // --- GESTIÓN DE OBSERVADORES (si necesitas desacoplar la UI) ---
    subscribe(eventType, callback) {
         if (!this.observers[eventType]) {
            this.observers[eventType] = [];
        }
        this.observers[eventType].push(callback);
    }
    unsubscribe(eventType, callback) {
         if (!this.observers[eventType]) return;
        this.observers[eventType] = this.observers[eventType].filter(obs => obs !== callback);
     }
    notifyObservers(eventType, data) {
         if (!this.observers[eventType]) return;
         this.observers[eventType].forEach(callback => {
             try {
                 callback(data);
             } catch (e) {
                 console.error(`Error en observador para ${eventType}:`, e);
             }
         });
    }

}
