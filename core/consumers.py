# core/consumers.py
import os
import json
import asyncio
import base64
from io import BytesIO
from datetime import datetime
import logging
import re
import uuid
from urllib.parse import urlparse
import traceback # Importar traceback para logs detallados

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.urls import reverse

from playwright.async_api import async_playwright
import jsonschema

from .models import Session, Screenshot, DataLayerCapture, Report

# Eliminar si no usas estas clases directamente aquí (parece que no)
# from validator.validator.datalayer_validator import DataLayerValidator
# from validator.parser.schema_builder import SchemaBuilder

# Configurar logger
logger = logging.getLogger(__name__)

class SessionConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket para manejar sesiones de validación de DataLayers
    """

    async def connect(self):
        """Establece la conexión WebSocket y configura el entorno"""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_group_name = f'session_{self.session_id}'
        logger.info(f"Intento de conexión WebSocket para sesión: {self.session_id}")

        # Unirse al grupo de la sesión
        await self.channel_layer.group_add(
            self.session_group_name,
            self.channel_name
        )

        # Inicializar variables
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.capture_interval = None # Podrías implementar captura periódica aquí
        self.session_obj = None
        self.reference_datalayers = None # Para almacenar el JSON parseado
        self.datalayer_schema = None # Podrías usarlo si quieres validación más profunda

        # Aceptar la conexión
        await self.accept()
        logger.info(f"Conexión WebSocket aceptada para sesión: {self.session_id}")

        # Cargar la sesión desde la base de datos
        try:
            self.session_obj = await self.get_session()
            if not self.session_obj:
                logger.error(f"Sesión no encontrada en DB: {self.session_id}")
                await self.send_error_message(f'Sesión no encontrada: {self.session_id}')
                await self.close()
                return

            # Cargar y parsear el JSON de referencia
            await self.load_reference_json()

        except Exception as e:
            logger.exception(f"Error durante la conexión/carga de sesión {self.session_id}: {str(e)}")
            await self.send_error_message(f'Error al cargar la sesión: {str(e)}')
            await self.close()
            return

        logger.info(f"Sesión {self.session_id} conectada y cargada.")
         # Enviar mensaje de éxito o estado inicial si es necesario
        await self.send(text_data=json.dumps({
            'action': 'status',
            'message': 'Conexión establecida. Inicializando navegador...'
        }))
        # Considera enviar un mensaje 'init' desde el cliente después de conectar,
        # o inicializar directamente aquí. Vamos a inicializar aquí por simplicidad ahora.
        # await self.handle_init() # Se llama desde el frontend ahora


    async def disconnect(self, close_code):
        """Cierra la conexión y libera recursos"""
        logger.info(f"Desconectando WebSocket para sesión {self.session_id}, código: {close_code}")

        # Detener la captura automática si está activa
        # (No implementado en este código, pero sería aquí)
        # if self.capture_interval:
        #     self.capture_interval.cancel()

        # Cerrar el navegador Playwright
        await self.close_browser()

        # Abandonar el grupo de Channels
        await self.channel_layer.group_discard(
            self.session_group_name,
            self.channel_name
        )
        logger.info(f"Limpieza completa para sesión {self.session_id}")


    async def receive(self, text_data):
        """Procesa los mensajes recibidos del cliente"""
        logger.debug(f"Mensaje recibido para sesión {self.session_id}: {text_data}")
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if not action:
                await self.send_error_message('Acción no especificada en el mensaje')
                return

            # Asegurarse que el navegador esté inicializado para acciones que lo requieran
            required_actions = ['navigation', 'capture', 'interaction', 'validation', 'report']
            # Init ahora no necesita navegador pre-inicializado
            # if action == 'init' and not self.browser:
            #    pass # Permitir init sin navegador

            if action in required_actions and not self.browser:
                logger.warning(f"Acción '{action}' recibida pero el navegador no está inicializado. Intentando inicializar...")
                await self.initialize_browser()
                if not self.browser: # Si la inicialización falló
                     await self.send_error_message("No se pudo inicializar el navegador para procesar la acción.")
                     return

            # Procesar según el tipo de acción
            handler_method = getattr(self, f'handle_{action}', None)
            if handler_method and callable(handler_method):
                await handler_method(data)
            else:
                # Manejar 'session' explícitamente si no tiene su propio handler
                if action == 'session':
                    await self.handle_session_action(data)
                else:
                    logger.warning(f"Acción desconocida recibida: {action}")
                    await self.send_error_message(f'Acción desconocida: {action}')

        except json.JSONDecodeError:
            logger.error("Error al decodificar JSON recibido")
            await self.send_error_message('Formato JSON inválido recibido')
        except Exception as e:
            logger.exception(f"Error al procesar mensaje para sesión {self.session_id}: {str(e)}")
            await self.send_error_message(f'Error interno al procesar mensaje: {str(e)}')


    # --------------------- MANEJADORES DE ACCIONES ---------------------

    async def handle_init(self, data=None): # data no se usa pero lo mantenemos por consistencia
        """Inicializa la sesión y envía el estado actual"""
        logger.info(f"Manejando acción 'init' para sesión {self.session_id}")
        # Inicializar el navegador si no lo está ya
        if not self.browser:
            await self.initialize_browser()
            if not self.browser: # Si falló la inicialización
                return

        # Enviar estado actual
        screenshots_count = await self.get_screenshots_count()
        datalayers_count = await self.get_datalayers_count()
        valid_count, invalid_count = await self.get_validation_stats()

        await self.send(text_data=json.dumps({
            'action': 'status',
            'current_url': self.page.url if self.page else self.session_obj.url, # Usa la URL real si la página existe
            'screenshot_count': screenshots_count,
            'datalayer_count': datalayers_count,
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'session_status': self.session_obj.status
        }))
        logger.info(f"Estado inicial enviado para sesión {self.session_id}")

        # Tomar una captura inicial (solo si la página está lista)
        if self.page:
            await self.capture_screenshot()
        else:
             logger.warning(f"No se tomó captura inicial, la página no estaba lista para sesión {self.session_id}")


    async def handle_navigation(self, data):
        """Maneja comandos de navegación"""
        command = data.get('command')
        logger.info(f"Manejando acción 'navigation', comando: {command} para sesión {self.session_id}")

        if not self.page:
             await self.send_error_message("Navegador no está listo para navegación.")
             return

        try:
            if command == 'back':
                await self.page.go_back(wait_until='domcontentloaded', timeout=30000)
            elif command == 'forward':
                await self.page.go_forward(wait_until='domcontentloaded', timeout=30000)
            elif command == 'reload':
                await self.page.reload(wait_until='domcontentloaded', timeout=30000)
            elif command == 'goto':
                url = data.get('url')
                if url:
                    logger.info(f"Navegando a: {url}")
                    await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
                else:
                     await self.send_error_message("Comando 'goto' requiere una URL.")
                     return
            else:
                await self.send_error_message(f'Comando de navegación desconocido: {command}')
                return

            # Esperar un poco a que la navegación surta efecto y JS se ejecute
            await asyncio.sleep(0.5)
            current_url = self.page.url
            logger.info(f"Navegación completada, URL actual: {current_url}")

            await self.send(text_data=json.dumps({
                'action': 'url_changed',
                'url': current_url
            }))

            # Guardar URL en el objeto de sesión (sin guardar en BD aquí, quizás al final?)
            self.session_obj.url = current_url
            # await self.update_session_url(current_url) # Opcional: guardar en cada paso

            await self.capture_screenshot()
            await self.capture_datalayer() # Capturar DL después de navegación

        except Exception as e:
             logger.exception(f"Error durante navegación ({command}): {str(e)}")
             await self.send_error_message(f'Error durante navegación: {str(e)}')


    async def handle_capture(self, data):
        """Maneja comandos de captura"""
        command = data.get('command')
        logger.info(f"Manejando acción 'capture', comando: {command} para sesión {self.session_id}")

        if not self.page:
             await self.send_error_message("Navegador no está listo para capturas.")
             return

        if command == 'datalayer':
            await self.capture_datalayer()
        elif command == 'screenshot':
            await self.capture_screenshot()
        else:
             await self.send_error_message(f'Comando de captura desconocido: {command}')


    # --- INICIO MODIFICACIÓN: Método handle_interaction corregido ---
    async def handle_interaction(self, data):
        """Maneja interacciones del usuario con el navegador"""
        command = data.get('command')
        logger.info(f"Manejando acción 'interaction', comando: {command} para sesión {self.session_id}")

        if not self.page:
            await self.send_error_message("Navegador no está listo para interacción.")
            return

        if command == 'click':
            x_percent = data.get('x')
            y_percent = data.get('y')

            if x_percent is None or y_percent is None:
                await self.send_error_message("Comando 'click' requiere coordenadas 'x' e 'y'.")
                return

            try:
                viewport_size = self.page.viewport_size
                if not viewport_size:
                    # Intentar obtener viewport de nuevo o usar uno por defecto?
                    logger.warning(f"No se pudo obtener viewport_size, reintentando...")
                    await asyncio.sleep(0.1)
                    viewport_size = self.page.viewport_size
                    if not viewport_size:
                        logger.error("Fallo al obtener viewport_size de nuevo.")
                        await self.send_error_message("No se pudo obtener el tamaño del viewport.")
                        return
                    logger.info(f"Viewport obtenido en reintento: {viewport_size}")


                width = viewport_size['width']
                height = viewport_size['height']

                # Calcular coordenadas absolutas y asegurarse que estén dentro de límites
                x = max(0, min(width - 1, int(width * x_percent)))
                y = max(0, min(height - 1, int(height * y_percent)))

                logger.info(f"Realizando clic en coordenadas: ({x}, {y}) (porcentajes: {x_percent:.3f}, {y_percent:.3f})")

                # Intentar identificar el elemento en esas coordenadas
                element_info = await self.page.evaluate("""(coords) => { // <-- Recibe un solo argumento 'coords'
                    const x = coords[0]; // <-- Obtiene x de coords
                    const y = coords[1]; // <-- Obtiene y de coords
                    const element = document.elementFromPoint(x, y);
                    if (element) {
                        // Verificar si es un elemento interactivo
                        const tagName = element.tagName.toLowerCase();
                        const isInteractive = element.closest('a, button, input, select, textarea, [onclick], [role="button"], [role="link"]') !== null;

                        return {
                            tagName: tagName,
                            id: element.id,
                            className: element.className,
                            isInteractive: isInteractive,
                            innerText: element.innerText?.substring(0, 50).replace(/\\n/g, ' ') || '' // Texto corto
                        };
                    }
                    return null;
                }""", [x, y]) # <--- Pasar [x, y] como UN solo argumento (lista)

                if element_info:
                    logger.info(f"Elemento identificado en coordenadas: {element_info}")

                    # Si es un elemento interactivo, intentar hacer clic directamente usando JavaScript como primer intento
                    # Esto puede ser más rápido pero podría no disparar todos los eventos JS del sitio
                    if element_info.get('isInteractive'):
                        try:
                            logger.debug("Intentando clic directo con JavaScript...")
                            click_success = await self.page.evaluate("""(coords) => { // <-- Recibe 'coords'
                                const x = coords[0]; // <-- Obtiene x
                                const y = coords[1]; // <-- Obtiene y
                                const element = document.elementFromPoint(x, y);
                                if (element) {
                                     // Intentar simular evento de mouse si click() no funciona
                                     const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                                     element.dispatchEvent(evt);
                                     //element.click(); // Método más simple pero menos fiable
                                     return true;
                                }
                                return false;
                            }""", [x, y]) # <--- Pasar [x, y]

                            if click_success:
                                logger.info("Clic JS ejecutado en elemento interactivo (o evento disparado)")
                                # Dar tiempo a que el JS de la página reaccione
                                await asyncio.sleep(0.3)
                            else:
                                logger.warning("Clic JS no pudo encontrar/clickear el elemento. Usando clic de mouse como fallback.")
                        except Exception as e:
                            logger.warning(f"Error al intentar clic JS: {str(e)}, usando clic de mouse como fallback")
                else:
                     logger.info("No se encontró información del elemento en las coordenadas. Procediendo con clic de mouse.")

                # Como fallback o si el clic JS falló, usar la secuencia de mouse de Playwright (más robusta)
                logger.info(f"Ejecutando secuencia mouse.move({x}, {y}), down, up...")
                await self.page.mouse.move(x, y, steps=5) # Añadir steps para suavizar el movimiento
                await asyncio.sleep(0.05) # Pausa muy corta
                await self.page.mouse.down()
                await asyncio.sleep(0.05) # Pausa muy corta
                await self.page.mouse.up()
                logger.info("Secuencia de clic de mouse completada.")

                # Esperar a que cualquier navegación o cambio en la página se complete
                try:
                    # Esperar un estado menos estricto o un timeout más corto
                    await self.page.wait_for_load_state("domcontentloaded", timeout=3000)
                    logger.info("Evento 'domcontentloaded' detectado después del clic.")
                except Exception as timeout_error:
                    # Ignorar timeout - no todas las interacciones causan navegación completa
                    logger.debug(f"Timeout esperando estado post-clic (esperado si no hay navegación completa): {timeout_error}")
                    pass # Continuar de todos modos

                # Espera final para asegurar renderizado y JS post-carga
                await asyncio.sleep(1.0)
                await self.capture_screenshot() # Captura después de la espera

                # Intentar capturar datalayer después de cada interacción
                try:
                    await self.capture_datalayer()
                except Exception as e:
                    logger.debug(f"Captura de datalayer post-clic falló (no crítico): {str(e)}")

            except Exception as e:
                # Log completo del traceback para depurar mejor
                logger.exception(f"Error CRÍTICO al realizar clic en sesión {self.session_id}: {str(e)}")
                # logger.error(traceback.format_exc()) # Descomentar si necesitas más detalle
                await self.send_error_message(f'Error al realizar clic: {str(e)}')

        elif command == 'type':
            selector = data.get('selector')
            text = data.get('text')

            if not selector or text is None: # Permite texto vacío
                await self.send_error_message("Comando 'type' requiere 'selector' y 'text'.")
                return

            try:
                # Asegurarse que el elemento existe y es visible/editable antes de interactuar
                # Timeout corto para no bloquear demasiado si no existe
                await self.page.wait_for_selector(selector, state='visible', timeout=5000)
                logger.debug(f"Elemento '{selector}' encontrado y visible.")

                # Limpiar campo primero (importante)
                await self.page.fill(selector, "")
                logger.debug(f"Campo '{selector}' limpiado.")
                await asyncio.sleep(0.1) # Pequeña pausa

                # Luego escribir usando type para simular mejor (con pequeño delay)
                await self.page.locator(selector).type(text, delay=50)
                logger.info(f"Texto ingresado en '{selector}': '{text}'")

                # Espera y captura
                await asyncio.sleep(0.5)
                await self.capture_screenshot()
            except Exception as e:
                logger.exception(f"Error al ingresar texto en sesión {self.session_id} (selector: '{selector}'): {str(e)}")
                await self.send_error_message(f'Error al ingresar texto en "{selector}": {str(e)}')
        else:
            await self.send_error_message(f'Comando de interacción desconocido: {command}')
    # --- FIN MODIFICACIÓN ---


    async def handle_validation(self, data):
        """Maneja comandos relacionados con la validación ( Placeholder )"""
        command = data.get('command')
        logger.info(f"Manejando acción 'validation', comando: {command} para sesión {self.session_id}")

        if command == 'check':
             valid_count, invalid_count = await self.get_validation_stats()
             total = valid_count + invalid_count
             message = f"Estadísticas actuales: {valid_count} válidos, {invalid_count} inválidos (Total: {total})."
             # Podrías añadir lógica para re-validar todo aquí si fuera necesario

             await self.send(text_data=json.dumps({
                'action': 'validation',
                'valid_count': valid_count,
                'invalid_count': invalid_count,
                'total': total,
                'message': message
             }))
        else:
             await self.send_error_message(f'Comando de validación desconocido: {command}')


    async def handle_session_action(self, data):
        """Maneja comandos relacionados con la sesión (stop)"""
        command = data.get('command')
        logger.info(f"Manejando acción 'session', comando: {command} para sesión {self.session_id}")

        if command == 'stop':
            await self.update_session_status('completed')
            logger.info(f"Sesión {self.session_id} marcada como completada.")

            await self.send(text_data=json.dumps({
                'action': 'session',
                'status': 'completed',
                'message': 'Sesión finalizada correctamente.'
            }))

            # Cerrar el navegador Playwright
            await self.close_browser()

            # Cerrar la conexión WebSocket desde el servidor
            await self.close(code=1000)
        else:
             await self.send_error_message(f'Comando de sesión desconocido: {command}')


    async def handle_report(self, data):
        """Maneja la generación de reportes"""
        command = data.get('command')
        logger.info(f"Manejando acción 'report', comando: {command} para sesión {self.session_id}")

        if command == 'generate':
            options = data.get('options', {})
            logger.info(f"Opciones de reporte recibidas: {options}")

            try:
                report_obj = await self.generate_report(options)
                report_url = reverse('report_detail', args=[report_obj.id]) # Asumiendo 'report_detail' es el nombre de la URL
                logger.info(f"Reporte generado para sesión {self.session_id}, ID: {report_obj.id}, URL: {report_url}")

                await self.send(text_data=json.dumps({
                    'action': 'report',
                    'status': 'generated',
                    'report_id': str(report_obj.id),
                    'report_url': report_url,
                    'message': 'Reporte generado correctamente.'
                }))

            except Exception as e:
                logger.exception(f"Error al generar reporte para sesión {self.session_id}: {str(e)}")
                await self.send_error_message(f'Error al generar reporte: {str(e)}')
        else:
             await self.send_error_message(f'Comando de reporte desconocido: {command}')


    # --------------------- FUNCIONES DE CAPTURA ---------------------

    async def capture_screenshot(self):
        """Captura una imagen del navegador y la envía al cliente"""
        if not self.page or not self.browser.is_connected():
            logger.warning(f"Intento de captura de pantalla sin página/navegador para sesión {self.session_id}")
            # await self.send_error_message("No se puede capturar pantalla, el navegador no está listo.")
            return # No enviar error aquí para no ser muy ruidoso, solo no hacer nada

        logger.debug(f"Capturando pantalla para sesión {self.session_id}...")
        try:
            # Captura JPEG con calidad moderada para ahorrar ancho de banda
            screenshot_bytes = await self.page.screenshot(type='jpeg', quality=70, timeout=10000) # Timeout para evitar bloqueos
            logger.debug(f"Screenshot bytes obtenidos ({len(screenshot_bytes)} bytes)")

            screenshot_obj = await self.save_screenshot(screenshot_bytes)
            if not screenshot_obj:
                 raise Exception("Fallo al guardar screenshot en DB.")

            logger.debug(f"Screenshot guardado en DB, ID: {screenshot_obj.id}, URL: {screenshot_obj.image.url}")

            await self.send(text_data=json.dumps({
                'action': 'screenshot',
                'image_url': screenshot_obj.image.url
            }))
            logger.debug(f"Mensaje de screenshot enviado para sesión {self.session_id}")

        except Exception as e:
            logger.exception(f"Error al capturar/guardar/enviar screenshot para sesión {self.session_id}: {str(e)}")
            await self.send_error_message(f'Error al capturar pantalla: {str(e)}')


    async def capture_datalayer(self):
        """Captura el DataLayer actual y lo procesa"""
        if not self.page or not self.browser.is_connected():
            logger.warning(f"Intento de captura de datalayer sin página/navegador para sesión {self.session_id}")
            # await self.send_error_message("No se puede capturar DataLayer, el navegador no está listo.")
            return

        logger.debug(f"Capturando DataLayer para sesión {self.session_id}...")
        try:
            # Este script intenta obtener el dataLayer de forma segura
            js_script = '''() => {
                try {
                    // Intentar acceder a window.dataLayer de forma segura
                    const dl = window.dataLayer;
                    if (typeof dl === 'undefined' || dl === null) {
                        return { status: 'not_found' }; // Indicar que no existe
                    }
                    if (!Array.isArray(dl)) {
                         return { status: 'not_array', type: typeof dl }; // Indicar si no es array
                    }
                    // Intentar clonar para evitar problemas de serialización circular
                    // Esto es una simplificación, puede fallar con objetos complejos
                    return { status: 'success', data: JSON.parse(JSON.stringify(dl)) };
                } catch (e) {
                    // Si falla la serialización, devolver un indicador de error o un array vacío
                    console.error('Error al serializar dataLayer:', e);
                    // Podríamos intentar devolver una versión más simple si es un array
                    if (Array.isArray(window.dataLayer)) {
                        // Devolver solo eventos si es posible (simplificación)
                         try {
                            // Solo devolver los últimos N eventos para no sobrecargar
                            const lastN = window.dataLayer.slice(-10); // Últimos 10
                            return { status: 'partial_success', data: JSON.parse(JSON.stringify(lastN)) };
                         } catch (mapError) {
                            return { status: 'error', message: `Error mapeando/serializando parcialmente: ${mapError.toString()}` };
                         }
                    }
                    return { status: 'error', message: `Error al serializar dataLayer completo: ${e.toString()}` };
                }
            }'''
            result = await self.page.evaluate(js_script)
            logger.debug(f"Resultado de obtención de DataLayer desde página: {result}")

            if result['status'] == 'not_found':
                logger.warning(f"No se encontró 'window.dataLayer' en la página para sesión {self.session_id}")
                await self.send_error_message('No se encontró el objeto dataLayer en la página.')
                return
            if result['status'] == 'not_array':
                 logger.warning(f"window.dataLayer no es un Array (tipo: {result['type']}) en sesión {self.session_id}")
                 await self.send_error_message(f"El objeto dataLayer encontrado no es un Array (tipo: {result['type']}).")
                 return
            if result['status'] == 'error':
                 logger.error(f"Error al obtener/serializar dataLayer desde JS: {result['message']}")
                 await self.send_error_message(f"Error interno al obtener dataLayer: {result.get('message', 'Error desconocido')}")
                 return

            captured_data = result.get('data', [])
            if not captured_data: # Si está vacío o no hay 'data'
                 logger.info(f"DataLayer capturado está vacío para sesión {self.session_id}")
                 # No enviar error, solo informar que está vacío si es necesario
                 # await self.send(...)
                 return

            # Aquí viene la validación contra el JSON de referencia (self.reference_datalayers)
            validation_results = self.validate_against_reference(captured_data)
            valid = validation_results['valid']
            errors = validation_results['errors']

            # El evento principal podría ser el último push si result es una lista
            event_name = "dataLayer Event" # Nombre por defecto
            last_event_obj = None
            if isinstance(captured_data, list) and len(captured_data) > 0:
                 # Buscar el último objeto en la lista que parezca un evento (tenga 'event')
                 for item in reversed(captured_data):
                    if isinstance(item, dict) and 'event' in item:
                        last_event_obj = item
                        event_name = item.get('event', event_name)
                        break
                 if not last_event_obj: # Si ninguno tiene 'event', usar el último elemento
                    last_event_obj = captured_data[-1]


            datalayer_obj = await self.save_datalayer(captured_data, valid, errors)
            logger.debug(f"DataLayer guardado en DB, ID: {datalayer_obj.id}")

            await self.send(text_data=json.dumps({
                'action': 'datalayer',
                'data': last_event_obj, # Enviar solo el último evento/objeto para simplificar UI? O todo 'captured_data'?
                'full_datalayer': captured_data, # Opcional: enviar todo si la UI lo necesita
                'valid': valid,
                'errors': errors,
                'id': str(datalayer_obj.id),
                'timestamp': datalayer_obj.created_at.isoformat(),
                'event': event_name # Nombre del evento inferido
            }))
            logger.debug(f"Mensaje de datalayer enviado para sesión {self.session_id}")

        except Exception as e:
            logger.exception(f"Error al capturar/validar/guardar dataLayer para sesión {self.session_id}: {str(e)}")
            await self.send_error_message(f'Error al capturar dataLayer: {str(e)}')


    # --------------------- FUNCIONES DE INICIALIZACIÓN Y CIERRE ---------------------

    async def initialize_browser(self):
     """Inicializa el navegador de Playwright"""
     if self.browser and self.browser.is_connected():
        logger.warning(f"Intento de inicializar navegador ya existente para sesión {self.session_id}")
        return # Ya está inicializado y conectado

     logger.info(f"Inicializando navegador para sesión {self.session_id}...")
     try:
        browser_type = os.environ.get('PLAYWRIGHT_BROWSER', self.session_obj.browser_type if self.session_obj else 'chromium')
        # Forzar headless=False ya que eliminamos la opción
        # headless = os.environ.get('PLAYWRIGHT_HEADLESS', 'false').lower() == 'true' # Ya no se usa
        logger.info(f"Configuración navegador: Tipo={browser_type}, Headless=False")

        self.playwright = await async_playwright().start()

        # Opciones optimizadas para ejecución en Docker y modo interactivo
        browser_options = {
            'headless': False, # Siempre interactivo
            'args': [
                '--no-sandbox', # Necesario en muchos entornos Docker
                '--disable-setuid-sandbox', # Alternativa a no-sandbox
                '--disable-dev-shm-usage', # Evita problemas con /dev/shm pequeño
                '--disable-gpu', # A menudo innecesario y problemático en Docker/Xvfb
                '--window-size=1280,720', # Tamaño inicial ventana
                # '--disable-web-security', # Considerar solo si hay problemas CORS/iframe extremos
                # '--allow-running-insecure-content' # Para contenido mixto si es necesario
            ],
            # Timeout más largo para el lanzamiento por si el sistema está lento
            'timeout': 90000 # 90 segundos
        }

        logger.debug(f"Lanzando navegador {browser_type} con opciones: {browser_options}")
        if browser_type == 'firefox':
            self.browser = await self.playwright.firefox.launch(**browser_options)
        elif browser_type == 'webkit':
            # Webkit puede tener menos argumentos soportados
            webkit_args = [arg for arg in browser_options['args'] if 'webkit' not in arg.lower()] # Filtrar args no soportados si se conocen
            browser_options['args'] = webkit_args
            self.browser = await self.playwright.webkit.launch(**browser_options)
        else: # Chromium por defecto
            self.browser = await self.playwright.chromium.launch(**browser_options)

        logger.info(f"Navegador {browser_type} lanzado. Creando contexto...")
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720}, # Sincronizado con window-size
            ignore_https_errors=True,  # Ayuda con sitios HTTPS problemáticos
            # has_touch=False, # Desactivar emulación touch que puede interferir
            # user_agent=... # Podrías definir un user agent específico si es necesario
            locale='es-ES', # Configurar locale
            timezone_id='America/Bogota' # Configurar timezone
        )
        logger.info("Contexto creado. Creando página...")

        self.page = await self.context.new_page()
        logger.info(f"Página creada para sesión {self.session_id}")

        # Configurar manejadores de eventos mejorados
        self.page.on("close", lambda: logger.info(f"Evento 'close' de página recibido para sesión {self.session_id}"))
        self.page.on("crash", lambda: logger.error(f"¡Página CRASHEADA para sesión {self.session_id}!"))
        self.page.on("pageerror", lambda exc: logger.error(f"Error JS en página para sesión {self.session_id}: {exc}"))
        # Filtrar mensajes de consola para reducir ruido
        self.page.on("console", lambda msg: asyncio.create_task(self.handle_console_message(msg)))
        self.page.on("dialog", lambda dialog: asyncio.create_task(self.handle_dialog(dialog)))

        # Añadir monitor de eventos de clic para depuración (ya estaba)
        # await self.page.evaluate("""() => {
        #     window.addEventListener('click', function(e) {
        #         console.log('Click detectado en página:', e.clientX, e.clientY, e.target.tagName);
        #     }, true);
        # }""")

        # Inyectar script para monitorizar dataLayer (asegurarse que se ejecuta)
        try:
            await self.page.evaluate("""() => {
                if (typeof window._dl_monitor_installed === 'undefined') {
                    window._dl_monitor_installed = true; // Marcar como instalado
                    if (typeof window.dataLayer === 'undefined') {
                        console.log('[DL Monitor] window.dataLayer no existe, inicializando...');
                        window.dataLayer = [];
                    } else {
                        console.log('[DL Monitor] window.dataLayer ya existe, tipo:', typeof window.dataLayer);
                    }

                    if (Array.isArray(window.dataLayer) && typeof window.dataLayer.push === 'function') {
                        const originalPush = window.dataLayer.push;
                        window.dataLayer.push = function() {
                            console.log('[DL Monitor] dataLayer.push detectado:', JSON.stringify(arguments[0] || null));
                            // Podríamos enviar un evento al backend aquí si quisiéramos captura en tiempo real
                            // window.ws.send(...) // Si tuviéramos acceso al websocket aquí
                            return originalPush.apply(this, arguments);
                        };
                        console.log('[DL Monitor] dataLayer.push instrumentado.');
                    } else {
                         console.warn('[DL Monitor] No se pudo instrumentar dataLayer.push (no es array o no tiene push).');
                    }
                } else {
                     console.log('[DL Monitor] Monitor ya instalado.');
                }
            }""")
            logger.info("Script de monitorización de DataLayer inyectado.")
        except Exception as script_error:
            logger.error(f"Error inyectando script de monitorización de DataLayer: {script_error}")


        # Navegar a la URL inicial
        initial_url = self.session_obj.url if self.session_obj else 'about:blank'
        if not initial_url or not initial_url.startswith('http'):
             logger.warning(f"URL inicial inválida ('{initial_url}'), usando about:blank")
             initial_url = 'about:blank'

        logger.info(f"Navegando a URL inicial: {initial_url}")
        # Aumentar timeout y usar 'load' o 'commit' podría ser más robusto que 'domcontentloaded' a veces
        await self.page.goto(initial_url, wait_until='load', timeout=90000) # Timeout más largo para carga inicial
        logger.info(f"Navegación inicial completada a: {self.page.url}")

        # Esperar un poco más para asegurar que la página esté completamente estable
        await asyncio.sleep(1.5)

        # Notificar URL actual al cliente
        await self.send(text_data=json.dumps({
            'action': 'url_changed',
            'url': self.page.url
        }))

        logger.info(f"Navegador inicializado correctamente para sesión {self.session_id}")
        await self.update_session_status('active')

     except Exception as e:
        logger.exception(f"FALLO CRÍTICO al inicializar navegador para sesión {self.session_id}: {str(e)}")
        await self.send_error_message(f'Error crítico al inicializar navegador: {str(e)}')
        await self.close_browser() # Intenta limpiar
        await self.update_session_status('error')


    async def handle_console_message(self, msg):
        """ Maneja mensajes de consola, filtrando ruido innecesario """
        msg_type = msg.type().lower()
        msg_text = msg.text()

        # Ignorar mensajes comunes/ruidosos (ajustar según sea necesario)
        ignored_patterns = [
            "Download the React DevTools",
            "Download the Vue Devtools",
            "JQMIGRATE",
            "[Fast Refresh]"
            "DevTools failed to load source map",
            "API KEY" # Si usas APIs con advertencias de clave
        ]
        if any(pattern in msg_text for pattern in ignored_patterns):
            return # Ignorar mensaje

        log_level = logging.DEBUG # Nivel por defecto
        if msg_type == 'error':
            log_level = logging.ERROR
        elif msg_type == 'warning':
            log_level = logging.WARNING
        elif msg_type == 'info':
            log_level = logging.INFO

        # Loguear con el nivel apropiado
        logger.log(log_level, f"Console [{msg_type.upper()}] en sesión {self.session_id}: {msg_text}")


    async def handle_dialog(self, dialog):
     """Maneja diálogos (alerts, confirms, prompts) que pueden aparecer"""
     try:
        logger.info(f"Diálogo detectado: Tipo={dialog.type}, Mensaje='{dialog.message()}'")
        # Aceptar automáticamente los diálogos para evitar bloqueos
        await dialog.accept()
        logger.info(f"Diálogo tipo '{dialog.type()}' aceptado automáticamente.")
     except Exception as e:
        logger.error(f"Error al manejar diálogo: {str(e)}")


    async def close_browser(self):
        """Cierra el navegador y libera recursos de Playwright"""
        if not self.browser and not self.playwright:
            logger.info(f"No hay navegador/playwright que cerrar para sesión {self.session_id}")
            return

        logger.info(f"Iniciando cierre del navegador para sesión {self.session_id}...")
        closed_something = False
        try:
            # Cerrar en orden inverso: página -> contexto -> navegador -> playwright
            if self.page:
                try:
                    await self.page.close(run_before_unload=True) # Intentar disparar eventos unload
                    self.page = None
                    closed_something = True
                    logger.info(f"Página cerrada para sesión {self.session_id}")
                except Exception as page_close_err:
                     logger.error(f"Error al cerrar página: {page_close_err}")

            if self.context:
                try:
                    await self.context.close()
                    self.context = None
                    closed_something = True
                    logger.info(f"Contexto cerrado para sesión {self.session_id}")
                except Exception as context_close_err:
                     logger.error(f"Error al cerrar contexto: {context_close_err}")

            if self.browser and self.browser.is_connected():
                try:
                    await self.browser.close()
                    self.browser = None
                    closed_something = True
                    logger.info(f"Navegador cerrado para sesión {self.session_id}")
                except Exception as browser_close_err:
                     logger.error(f"Error al cerrar navegador: {browser_close_err}")

            if self.playwright:
                try:
                    await self.playwright.stop()
                    self.playwright = None
                    closed_something = True
                    logger.info(f"Playwright detenido para sesión {self.session_id}")
                except Exception as playwright_stop_err:
                     logger.error(f"Error al detener Playwright: {playwright_stop_err}")


            if closed_something:
                 logger.info(f"Recursos de Playwright liberados para sesión {self.session_id}")
            else:
                 logger.info(f"No se cerraron recursos de Playwright activamente (posiblemente ya cerrados) en sesión {self.session_id}")

        except Exception as e:
            logger.exception(f"Error durante el cierre general del navegador para sesión {self.session_id}: {str(e)}")


    # --------------------- FUNCIONES DE BASE DE DATOS ---------------------

    @database_sync_to_async
    def get_session(self):
        """Obtiene la sesión de la base de datos"""
        try:
            # Usamos select_related para precargar el archivo JSON si es necesario más adelante
            return Session.objects.select_related(None).get(id=self.session_id)
        except Session.DoesNotExist:
            logger.error(f"Session.DoesNotExist en get_session para ID: {self.session_id}")
            return None
        except Exception as e:
             logger.exception(f"Excepción inesperada en get_session para ID {self.session_id}: {e}")
             return None


    @database_sync_to_async
    def load_reference_json(self):
        """Carga y parsea el archivo JSON de referencia desde el objeto Session"""
        if not self.session_obj or not self.session_obj.json_file:
            logger.warning(f"No hay archivo JSON de referencia para la sesión {self.session_id}")
            self.reference_datalayers = []
            return

        try:
            # Asegurarse de que el archivo está al inicio
            self.session_obj.json_file.seek(0)
            json_content = self.session_obj.json_file.read().decode('utf-8')
            self.reference_datalayers = json.loads(json_content)
            logger.info(f"Archivo JSON de referencia cargado para sesión {self.session_id}. {len(self.reference_datalayers)} eventos de referencia.")
            # Aquí podríamos construir el esquema de validación si fuera necesario
            # self.datalayer_schema = self.build_validation_schema(self.reference_datalayers)

        except json.JSONDecodeError as json_err:
            logger.error(f"Error de formato JSON en archivo de referencia para sesión {self.session_id}: {json_err}")
            self.reference_datalayers = []
            asyncio.create_task(self.send_error_message(f"Error de formato en archivo JSON de referencia: {json_err}"))
        except Exception as e:
            logger.exception(f"Error al cargar o parsear JSON de referencia para sesión {self.session_id}: {str(e)}")
            self.reference_datalayers = []
            # Enviar error al cliente también
            asyncio.create_task(self.send_error_message(f"Error al procesar archivo JSON de referencia: {str(e)}"))


    @database_sync_to_async
    def update_session_status(self, status):
        """Actualiza el estado de la sesión en la BD"""
        try:
            # Refrescar el objeto desde la BD por si acaso antes de guardar
            session_obj = Session.objects.get(id=self.session_id)
            if session_obj.status != status:
                session_obj.status = status
                session_obj.save(update_fields=['status'])
                # Actualizar también el objeto en memoria para consistencia
                self.session_obj.status = status
                logger.info(f"Estado de sesión {self.session_id} actualizado a: {status}")
        except Session.DoesNotExist:
             logger.error(f"Session.DoesNotExist al intentar actualizar estado de sesión {self.session_id} a {status}")
        except Exception as e:
             logger.exception(f"Error al actualizar estado de sesión {self.session_id} a {status}: {e}")


    @database_sync_to_async
    def save_screenshot(self, image_bytes):
        """Guarda una captura de pantalla en la base de datos y devuelve el objeto"""
        if not self.session_obj: return None
        current_url = "N/A"
        try:
            # Intentar obtener la URL actual de forma segura
            if self.page and self.browser.is_connected():
                current_url = self.page.url
            else:
                 logger.warning("No se pudo obtener URL actual para guardar screenshot (page/browser no listo)")

            filename = f"scr_{self.session_id}_{uuid.uuid4().hex[:6]}.jpg"

            screenshot = Screenshot(
                session=self.session_obj,
                url=current_url
            )
            screenshot.image.save(filename, ContentFile(image_bytes), save=True)
            logger.debug(f"Screenshot guardado: {filename} para URL {current_url}")
            return screenshot
        except Exception as e:
             logger.exception(f"Error al guardar screenshot en DB para sesión {self.session_id} (URL: {current_url}): {e}")
             return None


    @database_sync_to_async
    def save_datalayer(self, data, is_valid=None, errors=None):
        """Guarda un DataLayer capturado en la base de datos"""
        if not self.session_obj: return None
        current_url = "N/A"
        try:
            # Intentar obtener la URL actual de forma segura
            if self.page and self.browser.is_connected():
                 current_url = self.page.url
            else:
                  logger.warning("No se pudo obtener URL actual para guardar datalayer (page/browser no listo)")

            datalayer_capture = DataLayerCapture(
                session=self.session_obj,
                url=current_url,
                data=data, # Guardar el datalayer completo capturado
                is_valid=is_valid,
                errors=errors or []
                # validated_data podría añadirse aquí si la validación produce datos estructurados
            )
            datalayer_capture.save()
            logger.debug(f"DataLayer guardado para URL {current_url}. Válido: {is_valid}")
            return datalayer_capture
        except Exception as e:
             logger.exception(f"Error al guardar datalayer en DB para sesión {self.session_id} (URL: {current_url}): {e}")
             return None


    @database_sync_to_async
    def get_screenshots_count(self):
        """Obtiene el número de capturas de pantalla de la sesión"""
        if not self.session_obj: return 0
        try:
            return Screenshot.objects.filter(session=self.session_obj).count()
        except Exception as e:
             logger.exception(f"Error al contar screenshots para sesión {self.session_id}: {e}")
             return 0

    @database_sync_to_async
    def get_datalayers_count(self):
        """Obtiene el número de DataLayers capturados en la sesión"""
        if not self.session_obj: return 0
        try:
            return DataLayerCapture.objects.filter(session=self.session_obj).count()
        except Exception as e:
             logger.exception(f"Error al contar datalayers para sesión {self.session_id}: {e}")
             return 0

    @database_sync_to_async
    def get_validation_stats(self):
        """Obtiene las estadísticas de validación (válidos/inválidos)"""
        if not self.session_obj: return 0, 0
        try:
            qs = DataLayerCapture.objects.filter(session=self.session_obj)
            valid_count = qs.filter(is_valid=True).count()
            invalid_count = qs.filter(is_valid=False).count()
            return valid_count, invalid_count
        except Exception as e:
             logger.exception(f"Error al obtener stats de validación para sesión {self.session_id}: {e}")
             return 0, 0


    @database_sync_to_async
    def generate_report(self, options=None):
        """Crea el objeto Report en la base de datos"""
        if not self.session_obj: raise ValueError("No hay sesión activa para generar reporte")
        options = options or {}
        title = options.get('title', f"Validación {self.session_obj.id} - {timezone.now().strftime('%Y-%m-%d')}")

        try:
            # 1. Obtener todos los DataLayers capturados para esta sesión
            datalayer_captures = list(DataLayerCapture.objects.filter(session=self.session_obj).order_by('created_at'))

            # 2. Obtener Screenshots (opcionalmente)
            screenshots = []
            if options.get('include_screenshots', True):
                 screenshots = list(Screenshot.objects.filter(session=self.session_obj).order_by('created_at'))

            # 3. Calcular estadísticas
            valid_count = sum(1 for dl in datalayer_captures if dl.is_valid is True)
            invalid_count = sum(1 for dl in datalayer_captures if dl.is_valid is False)
            total_validated = valid_count + invalid_count # Total de DLs que fueron validados (no necesariamente todos los capturados)
            success_percent = round((valid_count / total_validated) * 100) if total_validated > 0 else 0
            is_valid_overall = success_percent >= 90 # Ejemplo: considerar válido si 90% o más son válidos

            # 4. Preparar datos para el campo JSON del reporte
            report_data = {
                'summary': {
                    'url': self.session_obj.url,
                    'session_id': str(self.session_obj.id),
                    'created_at': self.session_obj.created_at.isoformat(),
                    'report_generated_at': timezone.now().isoformat(),
                    'total_datalayers_captured': len(datalayer_captures),
                    'valid_count': valid_count,
                    'invalid_count': invalid_count,
                    'success_percent': success_percent,
                    'is_valid_overall': is_valid_overall
                },
                'details': [
                    {
                        'index': i,
                        'url': dl.url,
                        'timestamp': dl.created_at.isoformat(),
                        'data': dl.data if options.get('include_raw_data', True) else {'event': dl.data[-1].get('event', 'N/A') if isinstance(dl.data, list) and dl.data else 'N/A'}, # Mostrar solo evento del último push si no raw
                        'is_valid': dl.is_valid,
                        'errors': dl.errors,
                        'validated_data': getattr(dl, 'validated_data', None) # Incluir si existe
                    } for i, dl in enumerate(datalayer_captures)
                ],
                'screenshots': [
                     {
                        'url': s.url,
                        'timestamp': s.created_at.isoformat(),
                        'image_url': s.image.url if s.image else None # Verificar si la imagen existe
                     } for s in screenshots
                ] if options.get('include_screenshots', True) else [],
                'reference_comparison': {
                    # Esta parte necesita la lógica de comparación real
                    'reference_events_count': len(self.reference_datalayers or []),
                    'matched_events': 0, # Calcular esto
                    'missing_events': 0, # Calcular esto
                    'extra_events': 0    # Calcular esto
                }
            }

            # 5. Crear y guardar el objeto Report
            report = Report(
                session=self.session_obj,
                title=title,
                is_valid=is_valid_overall,
                data=report_data
                # Los archivos (HTML, PDF, etc.) se generarían y adjuntarían después si es necesario
            )
            report.save()
            logger.info(f"Objeto Report creado en DB con ID: {report.id}")
            return report

        except Exception as e:
             logger.exception(f"Error CRÍTICO al generar datos para el reporte {self.session_id}: {e}")
             raise # Relanzar la excepción para que se maneje arriba


    # --------------------- FUNCIONES DE UTILIDAD Y VALIDACIÓN ---------------------

    def validate_against_reference(self, captured_datalayer_list):
        """
        Valida una lista de datalayers capturados contra la lista de referencia.
        Esta es una validación simplificada basada en eventos y propiedades clave.
        """
        results = {'valid': True, 'errors': []}
        if not self.reference_datalayers:
            # No es un error si no hay referencia, simplemente no se valida
            # results['errors'].append("No hay DataLayers de referencia cargados para comparar.")
            # results['valid'] = False # Considerar inválido si no hay referencia? O solo warning?
            logger.info(f"No hay JSON de referencia para sesión {self.session_id}, no se realizará validación.")
            return {'valid': None, 'errors': ['No hay JSON de referencia.']} # Indicar que no se validó

        # Ejemplo: Validar el último evento capturado (simplificación)
        if not captured_datalayer_list or not isinstance(captured_datalayer_list, list):
             results['errors'].append("No hay DataLayers capturados válidos para validar.")
             results['valid'] = False
             return results

        last_event_captured = None
        # Buscar el último objeto en la lista que sea un diccionario y tenga 'event'
        for item in reversed(captured_datalayer_list):
            if isinstance(item, dict) and 'event' in item:
                last_event_captured = item
                break

        if not last_event_captured:
             # Si no hay evento explícito, no podemos comparar fácilmente. Marcar como no validado.
             results['errors'].append("No se encontró un evento explícito ('event': '...') en el último push del DataLayer capturado.")
             results['valid'] = None # Indicar que no se pudo validar vs referencia
             return results

        event_name = last_event_captured.get('event')
        logger.debug(f"Validando evento capturado: '{event_name}' contra referencia...")

        # Buscar un evento coincidente en la referencia
        matching_ref = None
        validation_errors_for_event = []
        found_match = False
        for ref_event in self.reference_datalayers:
            # Solo comparar si es un diccionario y el nombre del evento coincide
            if isinstance(ref_event, dict) and ref_event.get('event') == event_name:
                found_match = True # Encontramos al menos un evento con el mismo nombre
                match = True # Asumir que coincide hasta encontrar diferencia
                # Comprobar propiedades clave (simplificado)
                # Iterar sobre las claves presentes en el evento de referencia
                for key, ref_value in ref_event.items():
                     # Ignorar la clave 'event' misma y valores nulos/vacíos en la referencia (asumir que no se validan)
                     if key == 'event' or ref_value is None or ref_value == '':
                         continue

                     captured_value = last_event_captured.get(key)

                     # Si la clave no existe en el capturado, es un error
                     if captured_value is None:
                          match = False
                          validation_errors_for_event.append(f"Propiedad requerida '{key}' falta en evento '{event_name}'.")
                          continue # Pasar a la siguiente clave

                     # Comparar valores (simplificado, considera convertir a string para comparar)
                     # Ignorar variables tipo {{variable}}
                     if isinstance(ref_value, str) and '{{' in ref_value and '}}' in ref_value:
                          continue # Es una variable, no comparar valor exacto

                     # Comparación simple (podría mejorarse para tipos)
                     if str(ref_value) != str(captured_value):
                         match = False
                         validation_errors_for_event.append(f"Propiedad '{key}' no coincide para evento '{event_name}'. Esperado: '{ref_value}', Capturado: '{captured_value}'")

                if match:
                     # Si todas las propiedades coinciden para este evento de referencia, lo consideramos válido
                     matching_ref = ref_event
                     validation_errors_for_event = [] # Limpiar errores si encontramos un match perfecto
                     break # Salir del bucle de referencia, encontramos un match válido

        # Evaluar resultados de la búsqueda
        if not found_match:
             results['errors'].append(f"No se encontró ningún evento de referencia con nombre '{event_name}'.")
             results['valid'] = False
        elif not matching_ref: # Se encontró el evento pero ninguna referencia coincidió perfectamente
             results['errors'].extend(validation_errors_for_event) # Añadir los errores del último intento de match
             results['valid'] = False
        elif results['errors']: # Si por alguna razón quedaron errores (no debería pasar si matching_ref se encontró)
             results['valid'] = False


        logger.debug(f"Resultado validación para evento '{event_name}': Válido={results['valid']}, Errores={results['errors']}")
        return results


    async def send_error_message(self, message):
        """Envía un mensaje de error estandarizado al cliente"""
        logger.error(f"Enviando error al cliente ({self.session_id}): {message}") # Loguear el error también
        await self.send(text_data=json.dumps({
            'action': 'error', # Cambiado de 'errorMessage' a 'error' para consistencia con JS
            'message': message
        }))
