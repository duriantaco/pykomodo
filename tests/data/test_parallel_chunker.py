import unittest
import os
import tempfile
import shutil
from src.multi_dirs_chunker import ParallelChunker, PriorityRule

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

    def test_should_ignore_file(self):
        c = ParallelChunker(max_chunk_size=1000) 
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
        c = ParallelChunker(
            equal_chunks=2,
            output_dir=d
        )
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
        """Test chunk file naming and numbering"""
        d = os.path.join(self.test_dir, "chunk_names")
        os.mkdir(d)
        c = ParallelChunker(equal_chunks=3, output_dir=d)
        c.process_directory(self.test_dir)
        
        files = sorted(os.listdir(d))
        self.assertEqual(files, ["chunk-0.txt", "chunk-1.txt", "chunk-2.txt"])

if __name__ == "__main__":
    unittest.main()