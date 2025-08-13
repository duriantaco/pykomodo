import os
import tempfile
import shutil
import unittest
import fitz
from pykomodo.pdf_processor import PDFProcessor

class _MemoryChunkWriter:
    def __init__(self):
        self.written = []

    def write_chunk(self, content_bytes, chunk_num):
        text = content_bytes.decode("utf-8", errors="replace")
        self.written.append((chunk_num, text))

class TestPDFProcessor(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pdf_path = os.path.join(self.tmpdir, "sample.pdf")
        doc = fitz.open()
        page = doc.new_page()
        text = (
            "Para1 line1 with several words here\n"
            "Para1 line2 continues even more words\n"
            "\n"
            "Para2 line1 more words for the second paragraph\n"
            "Para2 line2 even more words\n"
        )
        rect = fitz.Rect(72, 72, 500, 800)
        page.insert_textbox(rect, text)
        doc.save(self.pdf_path)
        doc.close()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_extract_text_and_paragraphs(self):
        proc = PDFProcessor(max_chunk_size=50)
        txt = proc.extract_text_from_pdf(self.pdf_path)
        self.assertIsInstance(txt, str)
        self.assertIn("Para1", txt)

        paras = proc.extract_pdf_paragraphs(self.pdf_path)
        self.assertGreaterEqual(len(paras), 1)
        joined = "\n".join(paras)
        self.assertIn("Para1", joined)
        self.assertIn("Para2", joined)

    def test_process_pdf_for_chunking_creates_multiple_chunks(self):
        proc = PDFProcessor(max_chunk_size=10)
        mem = _MemoryChunkWriter()
        next_idx = proc.process_pdf_for_chunking(self.pdf_path, start_idx=0, chunk_writer=mem)

        self.assertGreaterEqual(len(mem.written), 2)
        self.assertEqual(next_idx, len(mem.written))

        combined = "\n".join(text for _, text in mem.written)
        self.assertIn(f"FILE: {self.pdf_path}", combined)
        self.assertIn("Para1", combined)
        self.assertIn("Para2", combined)

    def test_missing_file_paths_are_handled(self):
        proc = PDFProcessor(max_chunk_size=10)
        self.assertEqual(proc.extract_text_from_pdf("no_such.pdf"), "")
        self.assertEqual(proc.extract_pdf_paragraphs("no_such.pdf"), [])

        mem = _MemoryChunkWriter()
        next_idx = proc.process_pdf_for_chunking("no_such.pdf", start_idx=0, chunk_writer=mem)
        self.assertEqual(next_idx, 1)
        self.assertEqual(len(mem.written), 1)
        idx, text = mem.written[0]
        self.assertEqual(idx, 0)
        self.assertIn("[Error processing PDF:", text)

if __name__ == "__main__":
    unittest.main()
