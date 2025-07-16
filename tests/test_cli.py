import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import sys
from io import StringIO

class TestCLIScript(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.file_txt = os.path.join(self.test_dir, "example.txt")
        with open(self.file_txt, "w", encoding="utf-8") as f:
            f.write("Some file contents\nFor testing the script.")
        
        self.file_py = os.path.join(self.test_dir, "example.py")
        with open(self.file_py, "w", encoding="utf-8") as f:
            f.write("def hello():\n    return 'world'\n\nclass Test:\n    pass\n")
        
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_equal_chunks_cli(self):
        from pykomodo.command_line import main 
        
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
        self.assertGreater(len(chunk_files), 0)

    def test_max_chunk_size_cli(self):
        from pykomodo.command_line import main 
        
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
        self.assertTrue(len(chunk_files) > 0)

    def test_max_tokens_cli(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-tokens', '100',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            with patch('pykomodo.token_chunker.TokenBasedChunker') as mock_chunker:
                mock_instance = MagicMock()
                mock_chunker.return_value = mock_instance
                
                try:
                    main()
                except SystemExit as e:
                    if e.code != 0:  
                        self.fail(f"CLI failed with exit code: {e.code}")
                
                mock_chunker.assert_called_once()
                mock_instance.process_directories.assert_called_once()

    def test_priority_rules_cli(self):
        from pykomodo.command_line import main 
        
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

    def test_ignore_patterns_cli(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--ignore', '*.txt',
            '--ignore', 'test_*',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

    def test_unignore_patterns_cli(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--unignore', '*.md',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

    def test_enhanced_chunker_cli(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--enhanced',
            '--context-window', '2048',
            '--min-relevance', '0.5',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            with patch('pykomodo.enhanced_chunker.EnhancedParallelChunker') as mock_chunker:
                mock_instance = MagicMock()
                mock_chunker.return_value = mock_instance
                
                try:
                    main()
                except SystemExit as e:
                    if e.code != 0:  
                        self.fail(f"CLI failed with exit code: {e.code}")
                
                mock_chunker.assert_called_once()
                call_args = mock_chunker.call_args[1]
                self.assertEqual(call_args['context_window'], 2048)
                self.assertEqual(call_args['min_relevance_score'], 0.5)

    def test_semantic_chunks_cli(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--semantic-chunks',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

    def test_file_type_filter_cli(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--file-type', 'py',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

    def test_dry_run_cli(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--dry-run',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")

    def test_verbose_cli(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--verbose',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                try:
                    main()
                except SystemExit as e:
                    if e.code != 0:  
                        self.fail(f"CLI failed with exit code: {e.code}")

    def test_missing_required_args(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertNotEqual(cm.exception.code, 0)

    def test_mutually_exclusive_args(self):
        from pykomodo.command_line import main 
        
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
            self.assertNotEqual(cm.exception.code, 0)

    def test_invalid_priority_format(self):
        from pykomodo.command_line import main 
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--priority', 'invalid_format',
            '--output-dir', self.output_dir
        ]
        
        with patch('sys.argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertNotEqual(cm.exception.code, 0)

    def test_version_flag(self):
        from pykomodo.command_line import main 
        
        test_args = [sys.argv[0], '--version']
        
        with patch('sys.argv', test_args):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)

    def test_multiple_directories(self):
        from pykomodo.command_line import main 
        
        test_dir2 = tempfile.mkdtemp()
        try:
            with open(os.path.join(test_dir2, "file2.txt"), "w") as f:
                f.write("Content in second directory")
            
            test_args = [
                sys.argv[0],  
                self.test_dir,
                test_dir2,
                '--max-chunk-size', '100',
                '--output-dir', self.output_dir
            ]
            
            with patch('sys.argv', test_args):
                try:
                    main()
                except SystemExit as e:
                    if e.code != 0:  
                        self.fail(f"CLI failed with exit code: {e.code}")
        finally:
            shutil.rmtree(test_dir2)

    def test_output_directory_creation(self):
        from pykomodo.command_line import main 
        
        non_existent_dir = os.path.join(self.test_dir, "non_existent", "output")
        
        test_args = [
            sys.argv[0],  
            self.test_dir,
            '--max-chunk-size', '100',
            '--output-dir', non_existent_dir
        ]
        
        with patch('sys.argv', test_args):
            try:
                main()
            except SystemExit as e:
                if e.code != 0:  
                    self.fail(f"CLI failed with exit code: {e.code}")
        
        self.assertTrue(os.path.exists(non_existent_dir))

if __name__ == "__main__":
    unittest.main()