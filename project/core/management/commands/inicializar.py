from django.core.management.base import BaseCommand
from core.models import Empresa

class Command(BaseCommand):
    help = 'Inicializa datos base del sistema para comenzar a cargar catálogos'

    def handle(self, *args, **kwargs):
        empresas = [
            ('1', 'CORPORACIÓN INOX J&S S.A.C.'),
            ('2', 'EMPRESA DISTRIBUIDORA DEL SUR S.A.C.'),
            ('3', 'COMERCIALIZADORA NORTE PERÚ S.R.L.')
        ]

        for empresa_id, nombre in empresas:
            empresa, created = Empresa.objects.get_or_create(
                empresa_id=empresa_id,
                defaults={'nombre': nombre}
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"Empresa creada: {nombre}"))
            else:
                self.stdout.write(f"Empresa ya existe: {nombre}")

        self.stdout.write(self.style.SUCCESS("Inicialización completa. Ahora puedes importar tus catálogos."))