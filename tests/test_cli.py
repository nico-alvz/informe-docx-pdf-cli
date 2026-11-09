import contextlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from pypdf import PdfReader, PdfWriter

from informe_pdf.cli import CompileError, annexes, compile_report, find_office, main


def docx(path, text):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>''')
        archive.writestr("_rels/.rels", '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>''')
        archive.writestr("word/document.xml", f'''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p><w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>''')


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "anexos"
        self.folder.mkdir()

    def test_order_is_natural_and_explicit_order_is_complete(self):
        for name in ("10.pdf", "2.docx", "1.PDF", "ignored.txt", "~$lock.docx"):
            (self.folder / name).touch()
        self.assertEqual([p.name for p in annexes(self.folder)], ["1.PDF", "2.docx", "10.pdf"])
        order = self.root / "order.txt"
        order.write_text("# comentario\n10.pdf\n1.PDF\n2.docx\n", encoding="utf-8")
        self.assertEqual(annexes(self.folder, order)[0].name, "10.pdf")
        for invalid in ("10.pdf\n", "10.pdf\n10.pdf\n", "unknown.pdf\n"):
            order.write_text(invalid, encoding="utf-8")
            with self.assertRaises(CompileError):
                annexes(self.folder, order)

    def test_invalid_input_returns_failure(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(self.root / "missing.docx")]), 1)

    def test_real_conversion_merge_and_failure_preserves_output(self):
        try:
            office = find_office()
        except CompileError:
            self.skipTest("LibreOffice no instalado")
        report = self.root / "informe con espacios.docx"
        docx(report, "Synthetic report")
        docx(self.folder / "02_anexo.docx", "Synthetic annex")
        pdf = self.folder / "01_anexo.pdf"
        with PdfWriter() as writer:
            writer.add_blank_page(width=400, height=500)
            writer.write(pdf)
        output = self.root / "final.pdf"
        original = report.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(compile_report(report, self.folder, output, office=office), 3)
        with PdfReader(output) as reader:
            self.assertIn("Synthetic report", reader.pages[0].extract_text())
            self.assertEqual(float(reader.pages[1].mediabox.width), 400)
            self.assertIn("Synthetic annex", reader.pages[2].extract_text())
            self.assertFalse(reader.metadata)
        self.assertEqual(original, report.read_bytes())
        before = output.read_bytes()
        with self.assertRaises(CompileError):
            compile_report(report, self.folder, output, office=office)
        pdf.write_bytes(b"not a pdf")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main([str(report), "--anexos", str(self.folder), "-o", str(output), "--force"]), 1)
        self.assertEqual(before, output.read_bytes())
        self.assertFalse(list(self.root.glob(".informe-pdf-*")))


if __name__ == "__main__":
    unittest.main()
