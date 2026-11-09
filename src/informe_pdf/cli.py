"""Conversión aislada con LibreOffice y concatenación con pypdf."""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from . import __version__


class CompileError(Exception):
    """Error que puede corregir el usuario."""


def natural_key(path):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                 for part in re.split(r"(\d+)", path.name)) + ((2, path.name),)


def annexes(folder, order=None):
    if not folder.is_dir():
        raise CompileError(f"No existe la carpeta de anexos: {folder}")
    files = sorted((p.resolve() for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in {".pdf", ".docx"}
                    and not p.name.startswith("~$")), key=natural_key)
    if order is None:
        return files
    names = [line.strip() for line in order.read_text(encoding="utf-8-sig").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    available = {p.name: p for p in files}
    if len(set(names)) != len(names):
        raise CompileError("El archivo de orden contiene nombres repetidos.")
    missing = set(available) - set(names)
    unknown = set(names) - set(available)
    if missing or unknown:
        raise CompileError(f"Orden incompleto o inválido. Sin listar: {sorted(missing)}; "
                           f"desconocidos: {sorted(unknown)}")
    return [available[name] for name in names]


def find_office(explicit=None):
    if explicit:
        candidate = shutil.which(explicit) or explicit
        if Path(candidate).is_file():
            return str(Path(candidate).resolve())
        raise CompileError(f"No se encontró LibreOffice: {explicit}")
    for name in ("libreoffice", "soffice", "soffice.exe"):
        candidate = shutil.which(name)
        if candidate:
            return candidate
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(variable)
        if base:
            candidate = Path(base) / "LibreOffice/program/soffice.exe"
            if candidate.is_file():
                return str(candidate)
    raise CompileError("Instala LibreOffice o indica su ejecutable con --libreoffice.")


def convert(source, work, office, timeout):
    work.mkdir()
    profile = work / "profile"
    command = [office, f"-env:UserInstallation={profile.as_uri()}", "--headless",
               "--convert-to", "pdf:writer_pdf_Export", "--outdir", str(work), str(source)]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise CompileError(f"LibreOffice superó {timeout}s al convertir {source.name}.") from exc
    pdf = work / source.with_suffix(".pdf").name
    if result.returncode or not pdf.is_file() or not pdf.stat().st_size:
        detail = (result.stderr or result.stdout).strip()
        raise CompileError(f"No se pudo convertir {source.name}: {detail or 'sin PDF de salida'}")
    return pdf


def compile_report(report, folder, output, *, order=None, office=None, timeout=180, force=False):
    report, folder, output = report.resolve(), folder.resolve(), output.resolve()
    if not report.is_file() or report.suffix.lower() != ".docx":
        raise CompileError(f"El informe debe ser un DOCX existente: {report}")
    inputs = [report, *annexes(folder, order)]
    if output.suffix.lower() != ".pdf":
        raise CompileError("La salida debe tener extensión .pdf.")
    if output in inputs or output.parent == folder:
        raise CompileError("Guarda el PDF final fuera de anexos y sin reemplazar entradas.")
    if output.exists() and not force:
        raise CompileError(f"La salida ya existe: {output}. Usa --force para reemplazarla.")
    office = find_office(office)
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        with tempfile.TemporaryDirectory(prefix="informe-pdf-") as temporary:
            root = Path(temporary).resolve()
            with PdfWriter() as writer:
                expected = 0
                for index, source in enumerate(inputs):
                    print(f"[{index + 1}/{len(inputs)}] {source.name}")
                    pdf = convert(source, root / str(index), office, timeout) if source.suffix.lower() == ".docx" else source
                    reader = PdfReader(pdf)
                    if reader.is_encrypted:
                        raise CompileError(f"El PDF está cifrado: {source.name}. Usa una copia sin contraseña.")
                    if not reader.pages:
                        raise CompileError(f"El PDF no tiene páginas: {source.name}")
                    expected += len(reader.pages)
                    writer.append(reader, import_outline=False)
                # Evita atribuir el PDF combinado al equipo o autor que lo compila.
                writer.metadata = None
                fd, name = tempfile.mkstemp(prefix=".informe-pdf-", suffix=".pdf", dir=output.parent)
                pending = Path(name)
                with os.fdopen(fd, "wb") as stream:
                    writer.write(stream)
            with PdfReader(pending) as verified:
                if len(verified.pages) != expected:
                    raise CompileError("La cantidad de páginas del PDF final no coincide.")
            if force:
                os.replace(pending, output)
            else:
                # Reserva exclusiva: tampoco sobrescribe si otro proceso creó la salida.
                with output.open("xb") as destination, pending.open("rb") as source:
                    try:
                        shutil.copyfileobj(source, destination)
                    except BaseException:
                        output.unlink(missing_ok=True)
                        raise
                pending.unlink()
            pending = None
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    print(f"PDF creado: {output} ({expected} páginas)")
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description="Une informe DOCX y anexos PDF/DOCX en un PDF final.")
    parser.add_argument("informe", nargs="?", type=Path, default=Path("informe.docx"))
    parser.add_argument("--anexos", type=Path, default=Path("anexos"))
    parser.add_argument("-o", "--salida", type=Path, default=Path("informe-final.pdf"))
    parser.add_argument("--orden", type=Path, help="TXT UTF-8 con todos los nombres de anexos, uno por línea")
    parser.add_argument("--libreoffice", help="Ruta al ejecutable soffice/libreoffice")
    parser.add_argument("--timeout", type=int, default=180, help="Segundos por DOCX (predeterminado: 180)")
    parser.add_argument("--force", action="store_true", help="Reemplazar una salida existente")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout debe ser mayor que cero")
    try:
        compile_report(args.informe, args.anexos, args.salida, order=args.orden,
                       office=args.libreoffice, timeout=args.timeout, force=args.force)
    except (CompileError, OSError, ValueError, PdfReadError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
