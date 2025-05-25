from django.core.management.base import BaseCommand
from core.models import Empresa, CanalCliente

class Command(BaseCommand):
    help = 'Inicializa datos base del sistema para comenzar a cargar catálogos'

    def handle(self, *args, **kwargs):
        # Empresas base
        empresas = [
            (1, 'CORPORACIÓN INOX J&S S.A.C.'),
            (2, 'EMPRESA DISTRIBUIDORA DEL SUR S.A.C.'),
            (3, 'COMERCIALIZADORA NORTE PERÚ S.R.L.')
        ]

        for id_empresa, nombre in empresas:
            empresa, created = Empresa.objects.get_or_create(
                id=id_empresa,
                defaults={'nombre': nombre}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Empresa creada: {nombre}"))
            else:
                self.stdout.write(f"Empresa ya existe: {nombre}")


        self.stdout.write(self.style.SUCCESS("Inicialización completa. Ahora puedes importar tus catálogos."))