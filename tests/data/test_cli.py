import unittest
import os
import tempfile
import shutil
from pykomodo.multi_dirs_chunker import ParallelChunker
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

    def test_equal_chunks_cli(self):
        from src.pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--equal-chunks', '5',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        self.assertEqual(len(chunk_files), 5, "Should create exactly 5 chunks")

    def test_max_chunk_size_cli(self):
        from src.pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        self.assertTrue(len(chunk_files) > 0, "Should create at least one chunk")

    def test_priority_rules_cli(self):
        from src.pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--priority', '*.txt,10',
            '--priority', '*.md,5',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

    def test_missing_required_args(self):
        from src.pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertNotEqual(cm.exception.code, 0, 
                "Should exit with error when missing required chunking argument")

    def test_mutually_exclusive_args(self):
        from src.pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--equal-chunks', '5',
            '--max-chunk-size', '100',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertNotEqual(cm.exception.code, 0, 
                "Should exit with error when both chunking arguments are provided")

if __name__ == "__main__":
    unittest.main()