# core/models.py
from django.db import models
from django.contrib.auth.models import User
import uuid
import os


def json_upload_path(instance, filename):
    """Define la ruta para los archivos JSON subidos"""
    return f"uploads/json/{instance.id}/{filename}"


def screenshot_upload_path(instance, filename):
    """Define la ruta para las capturas de pantalla"""
    return f"uploads/screenshots/{instance.session.id}/{filename}"


class ValidationSession(models.Model):
    """Modelo para sesiones de validación"""

    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("running", "En ejecución"),
        ("completed", "Completada"),
        ("failed", "Fallida"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    url = models.URLField(max_length=500)
    reference_json = models.FileField(upload_to=json_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        return f"Sesión {self.id} - {self.url}"


class ScreenshotCapture(models.Model):
    """Modelo para capturas de pantalla durante la sesión"""

    session = models.ForeignKey(
        ValidationSession, on_delete=models.CASCADE, related_name="screenshots"
    )
    screenshot = models.ImageField(upload_to=screenshot_upload_path)
    timestamp = models.DateTimeField(auto_now_add=True)
    page_url = models.URLField(max_length=500)

    def __str__(self):
        return f"Captura para {self.session.id} en {self.timestamp}"


class DataLayerCapture(models.Model):
    """Modelo para datos de DataLayers capturados durante la sesión"""

    session = models.ForeignKey(
        ValidationSession, on_delete=models.CASCADE, related_name="datalayers"
    )
    page_url = models.URLField(max_length=500)
    datalayer_json = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DataLayer para {self.session.id} en {self.timestamp}"


class ValidationReport(models.Model):
    """Modelo para reportes de validación generados"""

    session = models.OneToOneField(
        ValidationSession, on_delete=models.CASCADE, related_name="report"
    )
    report_html = models.FileField(upload_to="reports/html/", null=True, blank=True)
    report_json = models.FileField(upload_to="reports/json/", null=True, blank=True)
    report_csv = models.FileField(upload_to="reports/csv/", null=True, blank=True)
    summary = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reporte para sesión {self.session.id}"
