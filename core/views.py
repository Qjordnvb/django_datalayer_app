from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.conf import settings

import os
import json
import uuid
from datetime import datetime

from .models import Session, Screenshot, DataLayerCapture, Report
from .forms import SessionForm


def home(request):
    """Vista de la página de inicio"""
    if request.method == 'POST':
        form = SessionForm(request.POST, request.FILES)
        if form.is_valid():
            session = form.save()
            messages.success(request, f'Sesión creada correctamente. Iniciando validación.')
            return redirect('session', session_id=session.id)
    else:
        form = SessionForm()

    # Obtener sesiones recientes
    recent_sessions = Session.objects.all().order_by('-created_at')[:5]

    return render(request, 'core/home.html', {
        'form': form,
        'recent_sessions': recent_sessions,
    })


def session_view(request, session_id):
    """Vista de la página de sesión de validación"""
    session = get_object_or_404(Session, id=session_id)

    # Si la sesión no está activa y no tiene reportes, redireccionar a la página de inicio
    if session.status == 'pending':
        session.status = 'active'
        session.save(update_fields=['status'])

    return render(request, 'core/session.html', {
        'session': session,
    })


def report_view(request, report_id):
    """Vista de la página de reporte de validación"""
    report = get_object_or_404(Report, id=report_id)

    return render(request, 'core/report.html', {
        'report': report,
    })


def sessions_list(request):
    """Vista para listar todas las sesiones"""
    # Filtros y búsqueda
    filter_status = request.GET.get('filter', 'all')
    search_query = request.GET.get('search', '')

    sessions = Session.objects.all()

    # Aplicar filtros
    if filter_status != 'all':
        sessions = sessions.filter(status=filter_status)

    # Aplicar búsqueda
    if search_query:
        sessions = sessions.filter(url__icontains=search_query) | sessions.filter(description__icontains=search_query)

    # Ordenar
    sessions = sessions.order_by('-created_at')

    # Paginación
    paginator = Paginator(sessions, 10)  # 10 sesiones por página
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/sessions.html', {
        'page_obj': page_obj,
        'filter': filter_status,
        'search_query': search_query,
    })


def reports_list(request):
    """Vista para listar todos los reportes"""
    # Filtros y búsqueda
    filter_valid = request.GET.get('filter', 'all')
    search_query = request.GET.get('search', '')

    reports = Report.objects.all()

    # Aplicar filtros
    if filter_valid == 'valid':
        reports = reports.filter(is_valid=True)
    elif filter_valid == 'invalid':
        reports = reports.filter(is_valid=False)

    # Aplicar búsqueda
    if search_query:
        reports = reports.filter(title__icontains=search_query) | reports.filter(session__url__icontains=search_query)

    # Ordenar
    reports = reports.order_by('-created_at')

    # Paginación
    paginator = Paginator(reports, 10)  # 10 reportes por página
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/reports.html', {
        'page_obj': page_obj,
        'filter': filter_valid,
        'search_query': search_query,
    })


def download_report(request, report_id, format_type):
    """Descarga un reporte en el formato especificado"""
    report = get_object_or_404(Report, id=report_id)

    if format_type == 'html' and report.html_file:
        return FileResponse(report.html_file, as_attachment=True, filename=f"reporte_{report_id}.html")
    elif format_type == 'pdf' and report.pdf_file:
        return FileResponse(report.pdf_file, as_attachment=True, filename=f"reporte_{report_id}.pdf")
    elif format_type == 'json' and report.json_file:
        return FileResponse(report.json_file, as_attachment=True, filename=f"reporte_{report_id}.json")
    elif format_type == 'csv' and report.csv_file:
        return FileResponse(report.csv_file, as_attachment=True, filename=f"reporte_{report_id}.csv")
    else:
        # Si el archivo no existe, generarlo al vuelo
        from validator.reporter.report_generator import ReportGenerator

        # Código para generar reporte al vuelo
        # En una implementación real, esto se haría de manera más completa

        # Por ahora, devolver un error 404
        raise Http404(f"Reporte en formato {format_type} no disponible")


def share_report(request, report_id):
    """Genera un enlace compartible para el reporte"""
    report = get_object_or_404(Report, id=report_id)

    # En una implementación real, aquí se generaría un enlace único
    # posiblemente con un token temporal

    share_url = request.build_absolute_uri(report.get_absolute_url())

    # Redireccionar de vuelta al reporte con un mensaje
    messages.success(request, f'Enlace para compartir: {share_url}')
    return redirect('report', report_id=report_id)


def placeholder_image(request):
    """Genera una imagen de marcador de posición"""
    # En una implementación real, esto generaría dinámicamente una imagen
    # Por ahora, devolvemos una respuesta simple
    return HttpResponse("Imagen de marcador de posición", content_type="image/png")
