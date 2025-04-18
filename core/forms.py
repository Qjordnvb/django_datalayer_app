# forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import URLValidator
import json
import jsonschema # Asegúrate de tener instalada esta librería: pip install jsonschema

from .models import Session

class SessionForm(forms.ModelForm):
    """Formulario para iniciar una nueva sesión de validación"""

    class Meta:
        model = Session
        fields = ['url', 'json_file', 'browser_type','description']
        widgets = {
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://ejemplo.com'}),
            'json_file': forms.FileInput(attrs={'class': 'form-control'}),
            'browser_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción opcional de la sesión'}),
        }
        help_texts = {
            'url': _('URL del sitio web que deseas validar'),
            'json_file': _('Archivo JSON con la estructura esperada de DataLayers'),
            'browser_type': _('Navegador a utilizar para la automatización'),
            'description': _('Descripción opcional para identificar esta sesión'),
        }

    def clean_url(self):
        """Valida que la URL sea válida"""
        url = self.cleaned_data.get('url')

        if not url:
            raise forms.ValidationError(_('La URL es obligatoria'))

        # Asegurarse de que la URL tiene un protocolo
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Validar la URL
        validator = URLValidator()
        try:
            validator(url)
        except forms.ValidationError:
            raise forms.ValidationError(_('La URL no es válida'))

        return url

    def clean_json_file(self):
        """Valida que el archivo sea un JSON válido con la estructura esperada"""
        json_file = self.cleaned_data.get('json_file')

        if not json_file:
            raise forms.ValidationError(_('El archivo JSON es obligatorio'))

        # Verificar extensión
        if not json_file.name.lower().endswith('.json'):
            raise forms.ValidationError(_('El archivo debe tener extensión .json'))

        # Verificar contenido JSON válido
        try:
            json_content = json_file.read().decode('utf-8')
            json_data = json.loads(json_content)

            # Resetear el puntero del archivo para futuras lecturas
            json_file.seek(0)

            schema = {
                "type": "array",  # El nivel superior es una lista (array)
                "items": {       # Cada item de la lista debe ser un objeto...
                    "type": "object",
                    # Define las claves que *deben* estar presentes en cada objeto
                    "required": ["event", "event_category", "event_action", "event_label"],
                    # Describe las propiedades y sus tipos esperados
                    "properties": {
                        "event": {"type": "string"},
                        "event_category": {"type": "string"},
                        "event_action": {"type": "string"},
                        "event_label": {"type": "string"},
                        # Para campos que pueden ser string o null:
                        "user_type": {"type": ["string", "null"]},
                        # Para campos que parecen ser string ("Yes", "False"):
                        "interaction": {"type": "string"},
                        "component_name": {"type": "string"},
                        "element_text": {"type": "string"},
                        # Puedes añadir más propiedades aquí si las tienes
                    },
                    # Permite claves adicionales no definidas explícitamente
                    "additionalProperties": True
                }
            }
            # --------------------------------------------------------------------------

            # Validar contra el nuevo esquema
            jsonschema.validate(instance=json_data, schema=schema)

        except UnicodeDecodeError:
            raise forms.ValidationError(_('El archivo no está codificado en UTF-8'))
        except json.JSONDecodeError:
            raise forms.ValidationError(_('El archivo no contiene JSON válido'))
        except jsonschema.exceptions.ValidationError as e:
            # Este error ahora indicaría un problema DENTRO de tu formato de lista
            # (ej. falta una clave requerida en un evento, o un tipo es incorrecto)
            raise forms.ValidationError(_(f'El JSON no tiene la estructura de lista de eventos esperada: {e.message}'))

        return json_file
