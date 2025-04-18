# core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
import json # Importado para formatted_data y formatted_errors

from .models import Session, Screenshot, DataLayerCapture, Report

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'url', 'status', 'browser_type', 'created_at', 'view_link')
    # Quitado 'headless' de list_filter:
    list_filter = ('status', 'browser_type', 'created_at')
    search_fields = ('url', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('id', 'url', 'status', 'description')
        }),
        ('Configuración', {
            # Quitado 'headless' de fields:
            'fields': ('json_file', 'browser_type')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def view_link(self, obj):
        # Asumiendo que tienes una URL nombrada 'session' en core/urls.py
        try:
            url = reverse('session', args=[obj.id])
            return format_html('<a href="{}" target="_blank">Ver sesión</a>', url)
        except Exception:
             # En caso de que la URL no exista o falle
            return "N/A"
    view_link.short_description = 'Ver'
    view_link.allow_tags = True # Necesario en versiones antiguas de Django


@admin.register(Screenshot)
class ScreenshotAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_link', 'url', 'created_at', 'show_image')
    list_filter = ('created_at',)
    search_fields = ('url', 'session__url') # Añadir búsqueda por URL de sesión
    readonly_fields = ('id', 'created_at', 'image_preview', 'session_link') # Añadir session_link

    def session_link(self, obj):
        try:
            url = reverse('admin:core_session_change', args=[obj.session.id])
            # Mostrar ID corto de la sesión
            return format_html('<a href="{}">{}...</a>', url, str(obj.session.id)[:8])
        except Exception:
            return "N/A"
    session_link.short_description = 'Sesión'

    def show_image(self, obj):
        if obj.image:
            return format_html('<a href="{}" target="_blank">Ver imagen</a>', obj.image.url)
        return "Sin imagen"
    show_image.short_description = 'Imagen'

    def image_preview(self, obj):
        if obj.image:
            # Limitar tamaño en admin para no sobrecargar
            return format_html('<img src="{}" style="max-width: 400px; max-height: 300px; object-fit: contain;" />', obj.image.url)
        return "Sin imagen"
    image_preview.short_description = 'Vista previa'


@admin.register(DataLayerCapture)
class DataLayerCaptureAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_link', 'url', 'is_valid', 'created_at')
    list_filter = ('is_valid', 'created_at')
    search_fields = ('url', 'session__url')
    readonly_fields = ('id', 'created_at', 'session_link', 'formatted_data', 'formatted_errors')

    def session_link(self, obj):
        try:
            url = reverse('admin:core_session_change', args=[obj.session.id])
            return format_html('<a href="{}">{}...</a>', url, str(obj.session.id)[:8])
        except Exception:
            return "N/A"
    session_link.short_description = 'Sesión'

    def formatted_data(self, obj):
        try:
            # Usa ensure_ascii=False para mostrar caracteres no latinos correctamente
            data_str = json.dumps(obj.data, indent=2, ensure_ascii=False)
            # Escapar HTML para seguridad
            escaped_str = format_html('{}', data_str)
            return format_html('<pre style="white-space: pre-wrap; word-wrap: break-word;">{}</pre>', escaped_str)
        except Exception as e:
            return f"Error al formatear JSON: {e}"
    formatted_data.short_description = 'Datos Capturados'

    def formatted_errors(self, obj):
        if not obj.errors:
            return "No hay errores"
        try:
            # Usa ensure_ascii=False
            errors_str = json.dumps(obj.errors, indent=2, ensure_ascii=False)
            escaped_str = format_html('{}', errors_str)
            return format_html('<pre style="white-space: pre-wrap; word-wrap: break-word;">{}</pre>', escaped_str)
        except Exception as e:
             return f"Error al formatear JSON de errores: {e}"
    formatted_errors.short_description = 'Errores de Validación'


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'session_link', 'is_valid', 'created_at', 'view_link')
    list_filter = ('is_valid', 'created_at')
    search_fields = ('title', 'session__url')
    readonly_fields = ('id', 'created_at', 'session_link', 'formatted_data')

    def session_link(self, obj):
        try:
            url = reverse('admin:core_session_change', args=[obj.session.id])
            return format_html('<a href="{}">{}...</a>', url, str(obj.session.id)[:8])
        except Exception:
            return "N/A"
    session_link.short_description = 'Sesión'

    def view_link(self, obj):
        # Asumiendo que tienes una URL nombrada 'report' en core/urls.py
        try:
            url = reverse('report', args=[obj.id])
            return format_html('<a href="{}" target="_blank">Ver reporte</a>', url)
        except Exception:
            return "N/A"
    view_link.short_description = 'Ver'
    view_link.allow_tags = True # Necesario en versiones antiguas

    def formatted_data(self, obj):
        try:
            # Usa ensure_ascii=False
            data_str = json.dumps(obj.data, indent=2, ensure_ascii=False)
            escaped_str = format_html('{}', data_str)
            return format_html('<pre style="white-space: pre-wrap; word-wrap: break-word;">{}</pre>', escaped_str)
        except Exception as e:
            return f"Error al formatear JSON de datos: {e}"
    formatted_data.short_description = 'Datos del reporte (JSON)'
