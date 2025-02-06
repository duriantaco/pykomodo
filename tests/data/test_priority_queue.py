import os
import shutil
import tempfile
from src.multi_dirs_chunker import ParallelChunker

def create_test_file(dir_path, filename, content=""):
    """Helper to create a test file with content"""
    file_path = os.path.join(dir_path, filename)
    with open(file_path, "w") as f:
        f.write(content)
    return file_path

def read_chunk_file(output_dir, chunk_filename):
    """Helper to read a chunk file's contents"""
    with open(os.path.join(output_dir, chunk_filename), "r") as f:
        return f.read()

class TestPriorityQueue:
    def setup_method(self):
        """Setup test environment before each test"""
        self.test_dir = tempfile.mkdtemp(prefix="komodo_test_")
        self.output_dir = tempfile.mkdtemp(prefix="komodo_output_")
        
    def teardown_method(self):
        """Cleanup after each test"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_basic_priority_ordering(self):
        """Test basic priority ordering with different file types"""
        try:
            test_files = [
                ("low.txt", "LOW_PRIO_CONTENT\n"),
                ("high.py", "HIGH_PRIO_CONTENT\n"), 
                ("medium.md", "MEDIUM_PRIO_CONTENT\n")
            ]

            for filename, content in test_files:
                create_test_file(self.test_dir, filename, content)

            priority_rules = [
                ("*.py", 100),
                ("*.md", 50),
                ("*.txt", 10)
            ]

            chunker = ParallelChunker(
                max_size=1024,
                output_dir=self.output_dir,
                priority_rules=priority_rules,
                binary_extensions=[],
                num_threads=1 
            )

            chunker.process_directories([self.test_dir])
            
            chunk_files = sorted(f for f in os.listdir(self.output_dir) 
                            if f.startswith("chunk-"))
            assert len(chunk_files) > 0, "No chunk files created"
            
            content = read_chunk_file(self.output_dir, chunk_files[0])
            
            py_pos = content.find("high.py")
            md_pos = content.find("medium.md") 
            txt_pos = content.find("low.txt")
            
            assert py_pos >= 0, "Python file not found"
            assert md_pos >= 0, "Markdown file not found"
            assert txt_pos >= 0, "Text file not found"
            assert py_pos < md_pos < txt_pos, "Files not in priority order"
            
        except Exception as e:
            print(f"Test failed: {str(e)}")
            raise

    def test_equal_priority_stable_sort(self):
        """Test that files with equal priority maintain stable ordering"""
        test_files = [
            ("a.py", "content_a"),
            ("b.py", "content_b"),
            ("c.py", "content_c")
        ]
        
        for filename, content in test_files:
            create_test_file(self.test_dir, filename, content)
        
        priority_rules = [("*.py", 100)]
        
        chunker = ParallelChunker(
            max_size=1024,
            output_dir=self.output_dir,
            priority_rules=priority_rules,
            binary_extensions=[],
            num_threads=1
        )
        
        chunker.process_directories([self.test_dir])
        chunker.close()
        
        chunk_files = sorted(f for f in os.listdir(self.output_dir) 
                           if f.startswith("chunk-"))
        content = read_chunk_file(self.output_dir, chunk_files[0])
        
        a_pos = content.find("a.py")
        b_pos = content.find("b.py")
        c_pos = content.find("c.py")
        
        assert all(pos >= 0 for pos in (a_pos, b_pos, c_pos)), "All files should be present"
        assert a_pos < b_pos < c_pos, "Equal priority files should be sorted alphabetically"

    def test_empty_and_edge_cases(self):
        """Test handling of empty files and edge cases"""
        test_files = [
            ("empty.py", ""),
            ("normal.py", "some content"),
            ("large.py", "x" * 1000)  
        ]
        
        for filename, content in test_files:
            create_test_file(self.test_dir, filename, content)
        
        priority_rules = [("*.py", 100)]
        
        chunker = ParallelChunker(
            max_size=1024,
            output_dir=self.output_dir,
            priority_rules=priority_rules,
            binary_extensions=[],
            num_threads=1
        )
        
        chunker.process_directories([self.test_dir])
        chunker.close()
        
        chunk_files = sorted(f for f in os.listdir(self.output_dir) if f.startswith("chunk-"))
        all_content = ""
        for chunk_filename in chunk_files:
            all_content += read_chunk_file(self.output_dir, chunk_filename)
        
        for filename, _ in test_files:
            assert filename in all_content, f"File {filename} should be present in output"

    def test_multiple_priority_levels(self):
        """Test handling of multiple priority levels with multiple files each"""
        test_files = [
            ("script1.py", "content1"),
            ("script2.py", "content2"),
            ("doc1.md", "doc1"),
            ("doc2.md", "doc2"),
            ("readme.txt", "readme"),
            ("notes.txt", "notes"),
        ]
        
        for filename, content in test_files:
            create_test_file(self.test_dir, filename, content)
        
        priority_rules = [
            ("*.py", 100),
            ("*.md", 50),
            ("*.txt", 10)
        ]
        
        chunker = ParallelChunker(
            max_size=1024,
            output_dir=self.output_dir,
            priority_rules=priority_rules,
            binary_extensions=[],
            num_threads=1
        )
        
        chunker.process_directories([self.test_dir])
        chunker.close()
        
        chunk_files = sorted(f for f in os.listdir(self.output_dir) 
                   if f.startswith("chunk-"))

        all_content = ""
        for chunk_filename in chunk_files:
            all_content += read_chunk_file(self.output_dir, chunk_filename)

        def min_pos(filenames):
            return min(all_content.find(f) for f in filenames)
            
        py_min = min_pos(["script1.py", "script2.py"])
        md_min = min_pos(["doc1.md", "doc2.md"])
        txt_min = min_pos(["readme.txt", "notes.txt"])

        assert py_min >= 0, "Python files should be present"
        assert md_min >= 0, "Markdown files should be present"
        assert txt_min >= 0, "Text files should be present"
        assert py_min < md_min < txt_min, "Files should be grouped by priority level"


if __name__ == "__main__":
    test = TestPriorityQueue()
    try:
        test.setup_method()
        print("Running basic priority ordering test...")
        test.test_basic_priority_ordering()
        print("Running equal priority stable sort test...")
        test.test_equal_priority_stable_sort()
        print("Running empty and edge cases test...")
        test.test_empty_and_edge_cases()
        print("Running multiple priority levels test...")
        test.test_multiple_priority_levels()
        print("All tests passed!")
    finally:
        test.teardown_method()