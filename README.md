# Informe DOCX → PDF

CLI para Windows y Linux: convierte `informe.docx`, convierte los anexos DOCX y
agrega todos los anexos PDF/DOCX al final, conservando sus páginas y tamaños.
Trabaja localmente, sin servicios ni cuentas. No incluye documentos de ejemplo reales.

## Instalación

Requiere Python **3.10 o posterior** y LibreOffice instalado.

En Windows, instala Python desde <https://www.python.org/downloads/windows/>
y LibreOffice desde <https://www.libreoffice.org/download/download-libreoffice/>.
En PowerShell, dentro de una carpeta de trabajo:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install https://github.com/nico-alvz/informe-docx-pdf-cli/archive/refs/tags/v1.0.0.zip
```

En Ubuntu/Debian:

```sh
sudo apt install python3 python3-venv libreoffice-writer
python3 -m venv .venv
.venv/bin/python -m pip install https://github.com/nico-alvz/informe-docx-pdf-cli/archive/refs/tags/v1.0.0.zip
```

También puedes descargar el código desde [Releases](https://github.com/nico-alvz/informe-docx-pdf-cli/releases),
descomprimirlo y ejecutar `python -m pip install .` con el Python del entorno virtual.
Las releases incluyen código fuente y un wheel Python universal; requieren Python
y LibreOffice. No son ejecutables autónomos.

## Compilar

Prepara esta estructura (la carpeta `anexos` puede estar vacía):

```text
trabajo/
  informe.docx
  anexos/
    01_especificacion.pdf
    02_diseno.docx
    03_resultados.pdf
```

Windows:

```powershell
.\.venv\Scripts\informe-pdf.exe informe.docx --anexos anexos -o informe-final.pdf
```

Linux:

```sh
.venv/bin/informe-pdf informe.docx --anexos anexos -o informe-final.pdf
```

Si usas los nombres predeterminados, basta con ejecutar `informe-pdf` desde el
entorno virtual activo. También funciona `python -m informe_pdf`.
Las rutas son relativas al directorio actual; usa comillas si tienen espacios.

El informe va primero. Los archivos de `anexos` se ordenan por nombre, sin
distinguir mayúsculas y con números naturales: `2` va antes de `10`. Para obtener
un orden idéntico entre equipos, usa nombres numerados únicos. Solo se toman
archivos del primer nivel con extensión `.docx` o `.pdf`; se omiten los temporales
de Word (`~$...`) y otros formatos. Si hay PDF y DOCX del mismo anexo, se incluyen
ambos: deja solo la versión que corresponda.

Para definir el orden, crea `orden.txt` en UTF-8 con **todos** los nombres exactos:

```text
03_resultados.pdf
01_especificacion.pdf
02_diseno.docx
```

```sh
informe-pdf --orden orden.txt -o entrega.pdf
```

Se permiten líneas vacías y comentarios que comienzan con `#`. Una lista
incompleta, duplicada o con nombres desconocidos genera un error.

Opciones útiles:

```sh
informe-pdf --help
informe-pdf --force                   # reemplaza una salida existente
informe-pdf --timeout 300             # máximo de segundos por DOCX
informe-pdf --libreoffice "/ruta/a/soffice"
```

En Windows, una ruta habitual para `--libreoffice` es
`"C:\Program Files\LibreOffice\program\soffice.exe"`; se detecta automáticamente
en las ubicaciones estándar. La salida debe quedar fuera de `anexos`.
Las entradas se conservan y la conversión usa directorios y perfiles temporales
aislados. Una conversión fallida devuelve código 1 y conserva una salida previa.

## Alcance y límites

Los anexos se agregan al final; no se intercalan mediante títulos del informe.
La CLI no modifica el DOCX, sus estilos ni sus índices. No agrega numeración
global, portadas ni marcas de agua. Los saltos de página y fuentes deben estar
preparados en los documentos originales. Instala las mismas fuentes en ambos
sistemas para reducir diferencias de paginación de LibreOffice.

Se valida que cada PDF tenga páginas y que el total final sea la suma de las
entradas. Se rechazan PDF cifrados. La combinación invalida firmas digitales del
PDF original; las firmas escaneadas siguen siendo contenido de página.
Los metadatos generales del PDF final se eliminan, pero el contenido y las
anotaciones pueden seguir conteniendo información personal: no es un anonimizador.

## Desarrollo y releases

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install build
python -m build
```

Las pruebas crean documentos sintéticos en temporales. La integración real se
ejecuta cuando LibreOffice está instalado; de lo contrario se omite explícitamente.
GitHub Actions verifica Windows y Linux. Al publicar una etiqueta `v*`, el flujo
de releases construye el wheel y el paquete fuente, genera SHA256 y los adjunta
a una release de GitHub. Licencia MIT.
