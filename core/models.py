import uuid
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class Session(models.Model):
    """Sesión de validación de DataLayers"""

    # Estados posibles de una sesión
    STATUS_CHOICES = (
        ('pending', _('Pendiente')),
        ('active', _('Activa')),
        ('completed', _('Completada')),
        ('error', _('Error')),
    )

    # Tipos de navegadores disponibles
    BROWSER_CHOICES = (
        ('chromium', _('Chromium')),
        ('firefox', _('Firefox')),
        ('webkit', _('WebKit')),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(_('URL'))
    json_file = models.FileField(_('Archivo JSON'), upload_to='uploads/json/')
    browser_type = models.CharField(_('Tipo de navegador'), max_length=20, choices=BROWSER_CHOICES, default='chromium')
    description = models.CharField(_('Descripción'), max_length=255, blank=True)
    status = models.CharField(_('Estado'), max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(_('Fecha de creación'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Fecha de actualización'), auto_now=True)

    class Meta:
        verbose_name = _('Sesión')
        verbose_name_plural = _('Sesiones')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.url} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse('session', kwargs={'session_id': self.id})


class Screenshot(models.Model):
    """Captura de pantalla del navegador"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='screenshots')
    url = models.URLField(_('URL'))
    image = models.ImageField(_('Imagen'), upload_to='screenshots/')
    created_at = models.DateTimeField(_('Fecha de captura'), auto_now_add=True)

    class Meta:
        verbose_name = _('Captura de pantalla')
        verbose_name_plural = _('Capturas de pantalla')
        ordering = ['-created_at']

    def __str__(self):
        return f"Captura de {self.url} ({self.created_at})"


class DataLayerCapture(models.Model):
    """Captura de DataLayer"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='datalayers')
    url = models.URLField(_('URL'))
    data = models.JSONField(_('Datos'))
    is_valid = models.BooleanField(_('Es válido'), null=True, blank=True)
    errors = models.JSONField(_('Errores'), default=list, blank=True)
    validated_data = models.JSONField(_('Datos validados'), null=True, blank=True)
    created_at = models.DateTimeField(_('Fecha de captura'), auto_now_add=True)

    class Meta:
        verbose_name = _('Captura de DataLayer')
        verbose_name_plural = _('Capturas de DataLayer')
        ordering = ['-created_at']

    def __str__(self):
        status = "Válido" if self.is_valid else "Inválido" if self.is_valid is not None else "Sin validar"
        return f"DataLayer de {self.url} - {status}"


class Report(models.Model):
    """Reporte de validación"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(_('Título'), max_length=255)
    is_valid = models.BooleanField(_('Es válido'), default=False)
    data = models.JSONField(_('Datos del reporte'))
    html_file = models.FileField(_('Archivo HTML'), upload_to='reports/html/', null=True, blank=True)
    pdf_file = models.FileField(_('Archivo PDF'), upload_to='reports/pdf/', null=True, blank=True)
    json_file = models.FileField(_('Archivo JSON'), upload_to='reports/json/', null=True, blank=True)
    csv_file = models.FileField(_('Archivo CSV'), upload_to='reports/csv/', null=True, blank=True)
    created_at = models.DateTimeField(_('Fecha de creación'), auto_now_add=True)

    class Meta:
        verbose_name = _('Reporte')
        verbose_name_plural = _('Reportes')
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('report', kwargs={'report_id': self.id})
