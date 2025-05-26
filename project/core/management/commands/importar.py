import random
import string
from django.core.management.base import BaseCommand
import pandas as pd
from core.models import (
    Empresa, CanalCliente, GrupoProveedor, Linea, Articulo, Vendedor
)

class Command(BaseCommand):
    help = 'Importa los catálogos desde archivos Excel'

    def handle(self, *args, **kwargs):
        try:
            empresa = Empresa.objects.get(empresa_id='1')
        except Empresa.DoesNotExist:
            self.stdout.write(self.style.ERROR("Debes ejecutar primero 'inicializar_sistema'"))
            return

        # === GRUPOS ===
        df = pd.read_excel('data/grupos.xlsx')
        for _, row in df.iterrows():
            empresa = Empresa.objects.get(empresa_id=row['empresa'])
            GrupoProveedor.objects.update_or_create(
                grupo_id=row['grupo_id'],
                defaults={
                    'empresa': empresa,
                    'codigo': row['codigo'],
                    'nombre': row['nombre'],
                    'estado': row['estado']
                }
            )
        self.stdout.write(self.style.SUCCESS("Grupos importados"))
        
        # === LINEAS ===
        df = pd.read_excel('data/lineas.xlsx')

        for _, row in df.iterrows():
            empresa = Empresa.objects.get(empresa_id=row['empresa'])
            grupo = GrupoProveedor.objects.get(grupo_id=row['grupo_id'])
            codigo = str(row['codigo'])

            # Verifica duplicidad en empresa + código
            while Linea.objects.filter(empresa=empresa, codigo=codigo).exists():
                letra_random = random.choice(string.ascii_uppercase)
                codigo = f"{str(row['codigo'])}{letra_random}"

            Linea.objects.update_or_create(
                linea_id=row['linea_id'],
                defaults={
                    'empresa': empresa,
                    'grupo': grupo,
                    'codigo': codigo,
                    'nombre': row['nombre'],
                    'estado': row['estado']
                }
            )

        self.stdout.write(self.style.SUCCESS("Líneas importadas"))
        
        # === ARTICULOS ===
        df = pd.read_excel('data/articulos.xlsx')
        for _, row in df.iterrows():
            empresa = Empresa.objects.get(empresa_id=row['empresa_id'])
            grupo = GrupoProveedor.objects.get(grupo_id=row['grupo_id'])
            linea = Linea.objects.get(linea_id=row['linea_id'])

            codigo_articulo = str(row['codigo_articulo'])

            # Evitar duplicados empresa + codigo_articulo
            while Articulo.objects.filter(empresa=empresa, codigo_articulo=codigo_articulo).exists():
                letra_random = random.choice(string.ascii_uppercase)
                codigo_articulo = f"{str(row['codigo_articulo'])}{letra_random}"
                print(f"Código duplicado para empresa {empresa}, se cambió '{row['codigo_articulo']}' por '{codigo_articulo}'")

            Articulo.objects.update_or_create(
                articulo_id=row['articulo_id'],
                defaults={
                    'empresa': empresa,
                    'codigo_articulo': codigo_articulo,
                    'codigo_barras': row.get('codigo_barras', ''),
                    'codigo_ean': row.get('codigo_ean', ''),
                    'descripcion': row['descripcion'],
                    'grupo': grupo,
                    'linea': linea,
                    'unidad_medida': row['unidad_medida'],
                    'unidad_compra': row['unidad_compra'],
                    'unidad_reparto': row['unidad_reparto'],
                    'unidad_bonificacion': row['unidad_bonificacion'],
                    'factor_reparto': row['factor_reparto'],
                    'factor_compra': row['factor_compra'],
                    'factor_bonificacion': row['factor_bonificacion'],
                    'tipo_afectacion': row['tipo_afectacion'],
                    'peso': row['peso'],
                    'tipo_producto': row['tipo_producto'],
                    'afecto_retencion': row['afecto_retencion'],
                    'afecto_detraccion': row['afecto_detraccion']
                }
            )

        self.stdout.write(self.style.SUCCESS("Artículos importados"))
        
        # === VENDEDORES ===
        df = pd.read_excel('data/vendedores.xlsx')
        for _, row in df.iterrows():
            canal_id = row['canal_id']

            # Crear el canal si no existe, usando canal_id como clave y también como nombre
            canal, _ = CanalCliente.objects.get_or_create(
                canal_id=canal_id,
                defaults={'nombre': canal_id}
            )

            Vendedor.objects.update_or_create(
                nro_documento=row['nro_documento'],
                defaults={
                    'tipo_identificacion_id': row['tipo_identificacion_id'],
                    'nombres': row['nombres'],
                    'direccion': row['Direccion'],
                    'nro_movil': row['nro_movil'],
                    'canal_id': canal.canal_id,  # canal_id es string (clave primaria personalizada)
                    'supervisor': row['supervisor'],
                    'correo_electronico': row['correo_electronico'],
                    'territorio': row['territorio'],
                    'rol_id': row['rol_id']
                }
            )
        self.stdout.write(self.style.SUCCESS("Vendedores importados"))
       

        self.stdout.write(self.style.SUCCESS("✅ Todos los catálogos fueron importados correctamente."))