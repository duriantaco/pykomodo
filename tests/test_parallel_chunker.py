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

    def test_dry_run_shows_files_without_creating_chunks(self):
        out_dir = os.path.join(self.test_dir, "dry_run_output")
        os.mkdir(out_dir)

        chunker = ParallelChunker(equal_chunks=2, output_dir=out_dir, dry_run=True)

        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output
        try:
            chunker.process_directory(self.test_dir)
        finally:
            sys.stdout = old_stdout

        output = captured_output.getvalue()
        self.assertIn("[DRY-RUN]", output)
        self.assertIn("file1.txt", output)

        chunk_files = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertEqual(len(chunk_files), 0)

    def test_ignores_git_files(self):
        chunker = ParallelChunker(max_chunk_size=1000) 
        chunker.current_walk_root = self.test_dir
        self.assertTrue(chunker.should_ignore_file(self.git_file))
        self.assertFalse(chunker.should_ignore_file(self.test_file_1))

    def test_detects_binary_files(self):
        chunker = ParallelChunker(max_chunk_size=1000)  
        self.assertTrue(chunker.is_binary_file(self.test_file_bin))
        self.assertFalse(chunker.is_binary_file(self.test_file_1))

    def test_loads_text_files(self):
        chunker = ParallelChunker(max_chunk_size=1000)
        chunker.process_directory(self.test_dir)
        file_paths = [x[0] for x in chunker.loaded_files]
        self.assertTrue(any("file1.txt" in path for path in file_paths))

    def test_priority_rules_work(self):
        rules = [("*.txt", 10), ("file2*", 20)]
        chunker = ParallelChunker(priority_rules=rules, max_chunk_size=1000) 
        chunker.process_directory(self.test_dir)
        priorities = [p for _, _, p in chunker.loaded_files]
        self.assertIn(10, priorities)
        self.assertIn(20, priorities)

    def test_priority_rules_default_to_zero(self):
        rules = [("*.md", 50), ("something*", 100)]
        chunker = ParallelChunker(priority_rules=rules, max_chunk_size=1000) 
        chunker.process_directory(self.test_dir)
        priorities = [p for _, _, p in chunker.loaded_files]
        self.assertTrue(all(x == 0 for x in priorities))

    def test_equal_chunks_creates_exact_number(self):
        out_dir = os.path.join(self.test_dir, "equal_out")
        os.mkdir(out_dir)
        chunker = ParallelChunker(equal_chunks=2, output_dir=out_dir)
        chunker.process_directory(self.test_dir)
        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertEqual(len(chunks), 2)

    def test_max_chunk_size_creates_multiple_chunks(self):
        out_dir = os.path.join(self.test_dir, "size_out")
        os.mkdir(out_dir)
        chunker = ParallelChunker(max_chunk_size=5, output_dir=out_dir)
        chunker.process_directory(self.test_dir)
        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertTrue(len(chunks) > 1)

    def test_handles_empty_files(self):
        empty_file = os.path.join(self.test_dir, "empty.txt")
        open(empty_file, "w").close()
        out_dir = os.path.join(self.test_dir, "empty_out")
        os.mkdir(out_dir)
        chunker = ParallelChunker(max_chunk_size=5, output_dir=out_dir)
        chunker.process_directory(self.test_dir)
        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertTrue(len(chunks) >= 1)

    def test_user_ignore_patterns(self):
        out_dir = os.path.join(self.test_dir, "ignore_out")
        os.mkdir(out_dir)
        chunker = ParallelChunker(output_dir=out_dir, user_ignore=["*file2.txt"], max_chunk_size=1000)
        chunker.process_directory(self.test_dir)
        loaded_names = [os.path.basename(x[0]) for x in chunker.loaded_files]
        self.assertNotIn("file2.txt", loaded_names)
        self.assertIn("file1.txt", loaded_names)

    def test_user_unignore_overrides_ignore(self):
        out_dir = os.path.join(self.test_dir, "unignore_out")
        os.mkdir(out_dir)
        chunker = ParallelChunker(
            output_dir=out_dir, 
            user_ignore=["*.txt"],
            user_unignore=["file2.txt"], 
            max_chunk_size=1000
        )
        chunker.process_directory(self.test_dir)
        loaded_names = [os.path.basename(x[0]) for x in chunker.loaded_files]
        self.assertIn("file2.txt", loaded_names)
        self.assertNotIn("file1.txt", loaded_names)

    def test_empty_directory_handling(self):
        empty_dir = os.path.join(self.test_dir, "empty_dir")
        os.mkdir(empty_dir)
        chunker = ParallelChunker(max_chunk_size=1000)
        chunker.process_directory(empty_dir)
        self.assertEqual(len(chunker.loaded_files), 0)

    def test_large_file_splitting(self):
        large_file = os.path.join(self.test_dir, "large.txt")
        with open(large_file, "w") as f:
            f.write("word " * 5000)
        out_dir = os.path.join(self.test_dir, "large_out")
        os.mkdir(out_dir)
        chunker = ParallelChunker(output_dir=out_dir, max_chunk_size=100)
        chunker.process_directory(self.test_dir)
        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertTrue(len(chunks) > 1)

    def test_many_files_with_threading(self):
        for i in range(50):
            with open(os.path.join(self.test_dir, f"file_{i}.txt"), "w") as f:
                f.write(f"Content {i}")

        chunker = ParallelChunker(max_chunk_size=1000, num_threads=4)
        chunker.process_directory(self.test_dir)
        self.assertGreater(len(chunker.loaded_files), 45)

    def test_invalid_encoding_doesnt_crash(self):
        invalid_file = os.path.join(self.test_dir, "invalid.txt")
        with open(invalid_file, "wb") as f:
            f.write(b"\xff\xfe\x00\x00Invalid UTF")

        chunker = ParallelChunker(max_chunk_size=1000)
        chunker.process_directory(self.test_dir)

    def test_chunk_file_naming(self):
        out_dir = os.path.join(self.test_dir, "naming_test")
        os.mkdir(out_dir)
        with open(os.path.join(self.test_dir, "file3.txt"), "w") as f:
            f.write("Third file\nWith text.")
        chunker = ParallelChunker(equal_chunks=3, output_dir=out_dir)
        chunker.process_directory(self.test_dir)
        files = sorted(os.listdir(out_dir))
        self.assertEqual(files, ["chunk-0.txt", "chunk-1.txt", "chunk-2.txt"])

    def test_semantic_chunking_python_files(self):
        out_dir = os.path.join(self.test_dir, "semantic_out")
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

        chunker = ParallelChunker(
            max_chunk_size=20,
            output_dir=out_dir,
            semantic_chunking=True
        )
        chunker.process_directory(self.test_dir)

        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertTrue(len(chunks) > 0)

        # Check if semantic info is in chunks
        found_func = False
        found_class = False
        for chunk_file in chunks:
            with open(os.path.join(out_dir, chunk_file), "r") as f:
                content = f.read()
                if "Function: func1" in content:
                    found_func = True
                if "Class: MyClass" in content:
                    found_class = True

        self.assertTrue(found_func or found_class)

    def test_semantic_chunking_syntax_error_fallback(self):
        out_dir = os.path.join(self.test_dir, "syntax_error_out")
        os.mkdir(out_dir)

        bad_py = os.path.join(self.test_dir, "bad.py")
        with open(bad_py, "w", encoding="utf-8") as f:
            f.write('''def broken_func()
    pass
    ''')

        chunker = ParallelChunker(
            max_chunk_size=20,
            output_dir=out_dir,
            semantic_chunking=True
        )
        chunker.process_directory(self.test_dir)

        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertTrue(len(chunks) > 0)

        with open(os.path.join(out_dir, chunks[0]), "r") as f:
            content = f.read()
            self.assertIn("bad.py", content)
            self.assertNotIn("Function: broken_func", content)

    def test_api_key_redaction(self):
        test_file = os.path.join(self.test_dir, "api_test.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Normal line\n")
            f.write("Short quoted: \"short\"\n")
            f.write("Long quoted: \"this_is_a_very_long_api_key_with_more_than_twenty_chars\"\n")
            f.write("Another normal line\n")

        out_dir = os.path.join(self.test_dir, "redaction_out")
        os.mkdir(out_dir)
        chunker = ParallelChunker(max_chunk_size=1000, output_dir=out_dir)
        chunker.process_file(test_file)

        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertEqual(len(chunks), 1)

        with open(os.path.join(out_dir, chunks[0]), "r") as f:
            content = f.read()

        self.assertIn("Normal line", content)
        self.assertIn("Short quoted: \"short\"", content)
        self.assertIn("[API_KEY_REDACTED]", content)
        self.assertNotIn("very_long_api_key", content)

    def test_file_type_filtering(self):
        py_file = os.path.join(self.test_dir, "test.py")
        js_file = os.path.join(self.test_dir, "test.js")
        
        with open(py_file, "w") as f:
            f.write("print('hello')")
        with open(js_file, "w") as f:
            f.write("console.log('hello')")

        chunker = ParallelChunker(max_chunk_size=1000, file_type="py")
        chunker.process_directory(self.test_dir)
        
        loaded_files = [os.path.basename(x[0]) for x in chunker.loaded_files]
        self.assertIn("test.py", loaded_files)
        self.assertNotIn("test.js", loaded_files)

    def test_process_single_file(self):
        out_dir = os.path.join(self.test_dir, "single_file_out")
        os.mkdir(out_dir)
        
        chunker = ParallelChunker(max_chunk_size=1000, output_dir=out_dir)
        chunker.process_file(self.test_file_1)
        
        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertEqual(len(chunks), 1)

    def test_custom_chunk_size_for_single_file(self):
        out_dir = os.path.join(self.test_dir, "custom_size_out")
        os.mkdir(out_dir)
        
        chunker = ParallelChunker(max_chunk_size=1000, output_dir=out_dir)
        chunker.process_file(self.test_file_1, custom_chunk_size=5)
        
        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertTrue(len(chunks) >= 1)

    def test_force_process_binary_file(self):
        out_dir = os.path.join(self.test_dir, "force_binary_out")
        os.mkdir(out_dir)
        
        chunker = ParallelChunker(max_chunk_size=1000, output_dir=out_dir)
        chunker.process_file(self.test_file_bin, force_process=True)
        
        chunks = [f for f in os.listdir(out_dir) if f.startswith("chunk-")]
        self.assertEqual(len(chunks), 1)

    def test_multiple_directories(self):
        second_dir = os.path.join(self.test_dir, "second")
        os.mkdir(second_dir)
        
        with open(os.path.join(second_dir, "another.txt"), "w") as f:
            f.write("content in second dir")

        chunker = ParallelChunker(max_chunk_size=1000)
        chunker.process_directories([self.test_dir, second_dir])
        
        file_paths = [x[0] for x in chunker.loaded_files]
        self.assertTrue(any("file1.txt" in path for path in file_paths))
        self.assertTrue(any("another.txt" in path for path in file_paths))

    def test_context_manager(self):
        with ParallelChunker(max_chunk_size=1000) as chunker:
            chunker.process_directory(self.test_dir)
            self.assertTrue(len(chunker.loaded_files) > 0)

    def test_gitignore_file_reading(self):
        gitignore_file = os.path.join(self.test_dir, ".gitignore")
        with open(gitignore_file, "w") as f:
            f.write("*.tmp\n")
            f.write("# comment\n")
            f.write("temp_dir/\n")

        tmp_file = os.path.join(self.test_dir, "test.tmp")
        with open(tmp_file, "w") as f:
            f.write("temp content")

        chunker = ParallelChunker(max_chunk_size=1000)
        chunker.process_directory(self.test_dir)
        
        loaded_files = [os.path.basename(x[0]) for x in chunker.loaded_files]
        self.assertNotIn("test.tmp", loaded_files)

if __name__ == "__main__":
    unittest.main()