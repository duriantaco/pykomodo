import unittest
import os
import tempfile
import shutil
from pykomodo.multi_dirs_chunker import ParallelChunker, PriorityRule
import io
import sys

class TestParallelChunker(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sub_dir = os.path.join(self.test_dir, "sub")
        os.mkdir(self.sub_dir)

        self.test_file_1 = os.path.join(self.test_dir, "file1.txt")
        self.test_file_2 = os.path.join(self.sub_dir, "file2.txt")
        self.git_dir = os.path.join(self.test_dir, ".git")

        os.mkdir(self.git_dir)
        self.git_file = os.path.join(self.git_dir, "config")
        self.test_file_bin = os.path.join(self.test_dir, "binary.bin")

        with open(self.test_file_1, "w") as f:
            f.write("This is a test file\nIt has some text.")
        with open(self.test_file_2, "w") as f:
            f.write("Another file\nWith more text.")
        with open(self.git_file, "w") as f:
            f.write("Git config")
        with open(self.test_file_bin, "wb") as f:
            f.write(b"\x00\xff\x10binary")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_dry_run_mode(self):
        out_dir = os.path.join(self.test_dir, "dry_run_output")
        os.mkdir(out_dir)

        c = ParallelChunker(equal_chunks=2, output_dir=out_dir, dry_run=True)

        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output
        try:
            c.process_directory(self.test_dir)
        finally:
            sys.stdout = old_stdout

        output_text = captured_output.getvalue()

        self.assertIn("[DRY-RUN]", output_text,
            "Should print a [DRY-RUN] header in the output.")

        chunk_files = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertEqual(len(chunk_files), 0,
            "No chunks should be generated in dry-run mode.")

        self.assertIn("file1.txt", output_text,
            "Should mention 'file1.txt' in the dry-run listing.")

    def test_should_ignore_file(self):
        c = ParallelChunker(max_chunk_size=1000) 
        c.current_walk_root = self.test_dir
        self.assertTrue(c.should_ignore_file(self.git_file))
        self.assertFalse(c.should_ignore_file(self.test_file_1))

    def test_is_binary_file(self):
        c = ParallelChunker(max_chunk_size=1000)  
        self.assertTrue(c.is_binary_file(self.test_file_bin))
        self.assertFalse(c.is_binary_file(self.test_file_1))

    def test_process_directory(self):
        c = ParallelChunker(max_chunk_size=1000)
        c.process_directory(self.test_dir)
        self.assertTrue(any("file1.txt" in x[0] for x in c.loaded_files))

    def test_priority_rules(self):
        r = [("*.txt", 10), ("file2*", 20)]
        c = ParallelChunker(priority_rules=r, max_chunk_size=1000) 
        c.process_directory(self.test_dir)
        ps = [p for _, _, p in c.loaded_files]
        self.assertIn(10, ps)
        self.assertIn(20, ps)

    def test_priority_rules_no_match(self):
        r = [("*.md", 50), ("something*", 100)]
        c = ParallelChunker(priority_rules=r, max_chunk_size=1000) 
        c.process_directory(self.test_dir)
        ps = [p for _, _, p in c.loaded_files]
        self.assertTrue(all(x == 0 for x in ps))

    def test_equal_chunks(self):
        d = os.path.join(self.test_dir, "out")
        os.mkdir(d)
        c = ParallelChunker(equal_chunks=2, output_dir=d)
        c.process_directory(self.test_dir)
        chunks = [f for f in os.listdir(d) if f.startswith("chunk-")]
        self.assertEqual(len(chunks), 2)

    def test_max_chunk_size(self):
        d = os.path.join(self.test_dir, "maxout")
        os.mkdir(d)
        c = ParallelChunker(max_chunk_size=5, output_dir=d)
        c.process_directory(self.test_dir)
        f = [x for x in os.listdir(d) if x.startswith("chunk-")]
        self.assertTrue(len(f) > 1)

    def test_max_chunk_size_empty_file(self):
        empty_file = os.path.join(self.test_dir, "empty.txt")
        open(empty_file, "w").close()
        d = os.path.join(self.test_dir, "maxout_empty")
        os.mkdir(d)
        c = ParallelChunker(max_chunk_size=5, output_dir=d)
        c.process_directory(self.test_dir)
        f = [x for x in os.listdir(d) if x.startswith("chunk-")]
        self.assertTrue(len(f) >= 1)

    def test_equal_chunks_exact(self):
        d = os.path.join(self.test_dir, "equal_chunks")
        os.mkdir(d)
        c = ParallelChunker(equal_chunks=2, output_dir=d)
        c.process_directory(self.test_dir)
        files = [x for x in os.listdir(d) if x.startswith("chunk-")]
        self.assertEqual(len(files), 2)

    def test_user_ignore_patterns(self):
        d = os.path.join(self.test_dir, "ignore_test")
        os.mkdir(d)
        c = ParallelChunker(output_dir=d, user_ignore=["*file2.txt"], max_chunk_size=1000)
        c.process_directory(self.test_dir)
        loaded = [os.path.basename(x[0]) for x in c.loaded_files]
        self.assertNotIn("file2.txt", loaded)
        self.assertIn("file1.txt", loaded)

    def test_user_unignore_patterns(self):
        d = os.path.join(self.test_dir, "unignore_test")
        os.mkdir(d)
        c = ParallelChunker(output_dir=d, user_ignore=["*.txt"],
                           user_unignore=["file2.txt"], max_chunk_size=1000)
        c.process_directory(self.test_dir)
        loaded = [os.path.basename(x[0]) for x in c.loaded_files]
        self.assertIn("file2.txt", loaded)
        self.assertNotIn("file1.txt", loaded)

    def test_no_files_collected(self):
        d = os.path.join(self.test_dir, "empty_dir")
        os.mkdir(d)
        c = ParallelChunker(max_chunk_size=1000)
        c.process_directory(d)
        self.assertEqual(len(c.loaded_files), 0)

    def test_large_chunk_split(self):
        large_file = os.path.join(self.test_dir, "large.txt")
        with open(large_file, "w") as f:
            f.write("word " * 5000)
        d = os.path.join(self.test_dir, "large_split_out")
        os.mkdir(d)
        c = ParallelChunker(output_dir=d, max_chunk_size=100)
        c.process_directory(self.test_dir)
        chunk_files = [x for x in os.listdir(d) if x.startswith("chunk-")]
        self.assertTrue(len(chunk_files) > 1)

    def test_concurrent_file_loading(self):
        """Test if parallel file loading works correctly with many files"""
        for i in range(100):
            with open(os.path.join(self.test_dir, f"file_{i}.txt"), "w") as f:
                f.write(f"Content {i}")

        c = ParallelChunker(max_chunk_size=1000, num_threads=4)
        c.process_directory(self.test_dir)

        self.assertGreater(len(c.loaded_files), 90)

    def test_invalid_encoding_handling(self):
        """Test handling of files with invalid encodings"""
        invalid_file = os.path.join(self.test_dir, "invalid.txt")
        with open(invalid_file, "wb") as f:
            f.write(b"\xff\xfe\x00\x00Invalid UTF")

        c = ParallelChunker(max_chunk_size=1000)
        c.process_directory(self.test_dir)

    def test_chunk_file_names(self):
        d = os.path.join(self.test_dir, "chunk_names")
        os.mkdir(d)
        with open(os.path.join(self.test_dir, "file3.txt"), "w") as f:
            f.write("Third file\nWith text.")
        c = ParallelChunker(equal_chunks=3, output_dir=d)
        c.process_directory(self.test_dir)
        files = sorted(os.listdir(d))
        self.assertEqual(files, ["chunk-0.txt", "chunk-1.txt", "chunk-2.txt"])

    def test_semantic_chunking_python_and_nonpy(self):
        """
        Test that when `semantic_chunking=True`:
          - .py files are hopefully split by AST function/class boundaries
          - Non-.py files are still chunked by size in fallback
        """
        out_dir = os.path.join(self.test_dir, "semantic_output")
        os.mkdir(out_dir)

        py_file = os.path.join(self.test_dir, "example.py")
        with open(py_file, "w", encoding="utf-8") as f:

            f.write('''def func1():
    pass
def func2():
    pass
class MyClass:
    def method1(self):
        pass
''')

        large_txt = os.path.join(self.test_dir, "large_nonpy.txt")
        with open(large_txt, "w", encoding="utf-8") as f:
            for i in range(20):
                f.write(f"Line {i}\n")

        c = ParallelChunker(
            max_chunk_size=20,
            output_dir=out_dir,
            semantic_chunking=True
        )
        c.process_directory(self.test_dir)

        chunk_files = sorted(cf for cf in os.listdir(out_dir) if cf.startswith("chunk-"))
        self.assertTrue(
            len(chunk_files) > 1,
            "Expected multiple chunks when semantic_chunking=True + small max_chunk_size"
        )

        py_chunks = []
        nonpy_chunks = []
        for cf in chunk_files:
            path_cf = os.path.join(out_dir, cf)
            with open(path_cf, "r", encoding="utf-8") as fp:
                content = fp.read()
                if "example.py" in content:
                    py_chunks.append(content)
                elif "large_nonpy.txt" in content:
                    nonpy_chunks.append(content)

        self.assertTrue(
            any("Function: func1" in chunk for chunk in py_chunks),
            "Should see 'Function: func1' in the Python chunk(s)."
        )
        self.assertTrue(
            any("Class: MyClass" in chunk for chunk in py_chunks),
            "Should see 'Class: MyClass' in the Python chunk(s)."
        )

        self.assertGreater(len(nonpy_chunks), 1,
            "The large_nonpy.txt file should produce more than one chunk under max_chunk_size=5.")
        self.assertTrue(
            any("Line 0" in c for c in nonpy_chunks),
            "Chunk for nonpy should contain 'Line 0'."
        )
        self.assertTrue(
            any("Line 19" in c for c in nonpy_chunks),
            "Should have final lines in a separate chunk for 'Line 19'."
        )

    def test_semantic_chunking_syntax_error(self):
        """
        Test that a .py file with invalid syntax gracefully falls back
        to a single chunk for that file.
        """
        out_dir = os.path.join(self.test_dir, "semantic_syntax_error")
        os.mkdir(out_dir)

        bad_py = os.path.join(self.test_dir, "bad.py")
        with open(bad_py, "w", encoding="utf-8") as f:
            f.write('''def broken_func()
    pass
    ''')

        c = ParallelChunker(
            max_chunk_size=20,
            output_dir=out_dir,
            semantic_chunking=True
        )
        c.process_directory(self.test_dir)

        chunk_files = sorted(cf for cf in os.listdir(out_dir) if cf.startswith("chunk-"))
        self.assertTrue(len(chunk_files) > 0, "We expect at least one chunk, even for the syntax error file.")

        with open(os.path.join(out_dir, chunk_files[0]), "r", encoding="utf-8") as fp:
            content = fp.read()
            self.assertIn("bad.py", content, "Should show fallback chunk referencing bad.py file.")
            self.assertNotIn("Function: broken_func", content,
                            "Should not see 'Function: broken_func' because AST parse failed.")

    def test_api_key_redaction(self):
        test_file = os.path.join(self.test_dir, "api_test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Normal line without quotes\n")
            f.write("Line with short quoted string: \"short\"\n")
            f.write("Line with exactly 20 characters: \"abcdefghijklmnopqrst\"\n")
            f.write("Line with 19 characters: \"abcdefghijklmnopqrs\"\n")
            f.write("Line with long quoted string: \"this_is_a_very_long_string_with_more_than_twenty_characters\"\n")
            f.write("Line with multiple quoted strings: \"short\" and \"long_string_with_more_than_twenty_characters\"\n")
            f.write("Line with special characters: \"!@#$%^&*()_long_string_with_more_than_twenty_characters\"\n")
            f.write("Line with interrupted long string: \"abcde!abcde!abcde!abcde\"\n")
            f.write("Line with long string not quoted: abcdefghijklmnopqrstuvwxyz\n")
            f.write("Another normal line\n")

        out_dir = os.path.join(self.test_dir, "api_redaction_output")
        os.mkdir(out_dir)
        c = ParallelChunker(max_chunk_size=1000, output_dir=out_dir)

        c.process_file(test_file)

        chunk_files = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertEqual(len(chunk_files), 1, "Should generate exactly one chunk file for the small file")

        with open(os.path.join(out_dir, chunk_files[0]), "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines()
        file_content_lines = lines[8:] 

        expected_lines = [
            "Normal line without quotes",
            "Line with short quoted string: \"short\"",
            "[API_KEY_REDACTED]",  
            "Line with 19 characters: \"abcdefghijklmnopqrs\"",
            "[API_KEY_REDACTED]", 
            "[API_KEY_REDACTED]", 
            "[API_KEY_REDACTED]",  
            "Line with interrupted long string: \"abcde!abcde!abcde!abcde\"",
            "Line with long string not quoted: abcdefghijklmnopqrstuvwxyz",
            "Another normal line"
        ]

        self.assertEqual(file_content_lines, expected_lines, "Chunk content does not match expected redacted output")

if __name__ == "__main__":
    unittest.main()