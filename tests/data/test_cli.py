import unittest
import os
import tempfile
import shutil
from src.multi_dirs_chunker import ParallelChunker
from unittest.mock import patch
import sys

class TestCLIScript(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.file_txt = os.path.join(self.test_dir, "example.txt")
        with open(self.file_txt, "w", encoding="utf-8") as f:
            f.write("Some file contents\nFor testing the script.")
        
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_basic_cli(self):
        from src.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--ignore', '*.md',
            '--priority-rule', '*.txt,10',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        self.assertTrue(len(chunk_files) > 0, f"No chunk files found in {self.output_dir}")

if __name__ == "__main__":
    unittest.main()