import unittest
import os
import tempfile
import shutil
from pykomodo.enhanced_chunker import EnhancedParallelChunker

class TestEnhancedParallelChunker(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
        self.python_file = os.path.join(self.test_dir, "example.py")
        with open(self.python_file, "w", encoding="utf-8") as f:
            f.write('''"""
                This is a test docstring.
                """
                import pandas as pd
                from datetime import datetime

                class TestClass:
                    def __init__(self):
                        pass
                        
                    def test_method(self):
                        # This is a comment
                        pass

                def standalone_function():
                    """Function docstring"""
                    return True
                ''')
        
        self.redundant_file = os.path.join(self.test_dir, "redundant.py")
        with open(self.redundant_file, "w", encoding="utf-8") as f:
            f.write('''def standalone_function():
                """Function docstring"""
                return True
            ''')
        
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_metadata_extraction(self):
        """Test if metadata is correctly extracted from files"""
        chunker = EnhancedParallelChunker(
            equal_chunks=1,
            output_dir=self.output_dir,
            extract_metadata=True
        )
        chunker.process_directory(self.test_dir)
        
        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        self.assertEqual(len(chunk_files), 1)
        
        with open(os.path.join(self.output_dir, chunk_files[0]), 'r') as f:
            content = f.read()
            
        self.assertIn('METADATA:', content)
        self.assertIn('FUNCTIONS: standalone_function, test_method', content)
        self.assertIn('CLASSES: TestClass', content)
        self.assertIn('IMPORTS: import pandas, from datetime', content)
        self.assertIn('This is a test docstring', content)

    def test_relevance_scoring(self):
        """Test if relevance scoring works correctly"""
        chunker = EnhancedParallelChunker(
            equal_chunks=1,
            output_dir=self.output_dir,
            min_relevance_score=0.5  
        )
        
        low_relevance = os.path.join(self.test_dir, "low_relevance.py")
        with open(low_relevance, "w") as f:
            f.write("# Just comments\n# More comments\n# Even more comments\nx = 1")
        
        chunker.process_directory(self.test_dir)
        
        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        for chunk_file in chunk_files:
            with open(os.path.join(self.output_dir, chunk_file), 'r') as f:
                content = f.read()
                if 'low_relevance.py' in content:
                    relevance_line = [l for l in content.split('\n') if 'RELEVANCE_SCORE:' in l][0]
                    score = float(relevance_line.split(':')[1].strip())
                    self.assertLess(score, 1.0)  

    def test_redundancy_removal(self):
        """Test if redundant content is properly removed"""
        chunker = EnhancedParallelChunker(
            equal_chunks=2,
            output_dir=self.output_dir,
            remove_redundancy=True
        )
        chunker.process_directory(self.test_dir)
        
        all_content = []
        chunk_files = sorted([f for f in os.listdir(self.output_dir) if f.startswith('chunk-')])
        for chunk_file in chunk_files:
            with open(os.path.join(self.output_dir, chunk_file), 'r') as f:
                all_content.append(f.read())
        
        redundant_count = sum(
            content.count('def standalone_function():') 
            for content in all_content
        )
        self.assertEqual(redundant_count, 1, "Redundant function should appear only once")

    def test_context_window_respect(self):
        """Test if chunks respect context window size"""
        small_window = 100
        chunker = EnhancedParallelChunker(
            equal_chunks=2,
            output_dir=self.output_dir,
            context_window=small_window
        )

        for f in os.listdir(self.test_dir):
            print(f"- {f}")
        
        chunker.process_directory(self.test_dir)
        
        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        
        for chunk_file in chunk_files:
            chunk_path = os.path.join(self.output_dir, chunk_file)
            try:
                with open(chunk_path, 'rb') as f:  
                    content = f.read()
                    size = len(content)
                    if size >= small_window * 1.5:
                        print(f"WARNING: Chunk too large! Size {size} exceeds limit {small_window * 1.5}")
                    self.assertLess(size, small_window * 1.5, 
                        f"Chunk {chunk_file} size {size} exceeds limit {small_window * 1.5}")
            except Exception as e:
                print(f"ERROR reading {chunk_file}: {str(e)}")
                raise

    def test_disable_features(self):
        """Test if features can be properly disabled"""
        chunker = EnhancedParallelChunker(
            equal_chunks=1,
            output_dir=self.output_dir,
            extract_metadata=False,
            add_summaries=False,
            remove_redundancy=False
        )
        chunker.process_directory(self.test_dir)
        
        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        with open(os.path.join(self.output_dir, chunk_files[0]), 'r') as f:
            content = f.read()
            self.assertNotIn('METADATA:', content)
            self.assertGreater(
                content.count('def standalone_function():'),
                1
            )

    def test_complex_metadata(self):
        """Test metadata extraction from more complex code structures"""
        complex_file = os.path.join(self.test_dir, "complex.py")
        with open(complex_file, "w") as f:
            f.write('''
                from typing import List, Optional
                import os.path as osp
                
                @decorator
                class ComplexClass:
                    """Class docstring"""
                    def __init__(self):
                        pass
                    
                    @property
                    def prop(self): 
                        return None
                        
                    async def async_method(self):
                        pass
            ''')
            
        chunker = EnhancedParallelChunker(equal_chunks=1, output_dir=self.output_dir)
        chunker.process_directory(self.test_dir)
        
        with open(os.path.join(self.output_dir, "chunk-0.txt"), 'r') as f:
            content = f.read()
            self.assertIn('async_method', content)
            self.assertIn('ComplexClass', content)
            self.assertIn('from typing import', content)

    def test_large_file_handling(self):
        """Test handling of large files with context window"""
        large_file = os.path.join(self.test_dir, "large.py")
        with open(large_file, "w") as f:
            f.write("x = 1\n" * 10000)  
            
        chunker = EnhancedParallelChunker(
            equal_chunks=2,
            output_dir=self.output_dir,
            context_window=1000,
            remove_redundancy=True
        )
        chunker.process_directory(self.test_dir)
        
        chunks = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        for chunk in chunks:
            with open(os.path.join(self.output_dir, chunk), 'r') as f:
                content = f.read()
                self.assertLess(len(content), 1000)

    def test_mixed_content_relevance(self):
        """Test relevance scoring with mixed content types"""
        mixed_file = os.path.join(self.test_dir, "mixed.py")
        with open(mixed_file, "w") as f:
            f.write('''
                # Configuration
                CONFIG = {
                    "key": "value"
                }
                
                def important_function():
                    """Critical business logic"""
                    pass
                    
                # Just some constants
                A = 1
                B = 2
                C = 3
            ''')
            
        chunker = EnhancedParallelChunker(
            equal_chunks=2,
            output_dir=self.output_dir,
            min_relevance_score=0.3
        )
        chunker.process_directory(self.test_dir)
        
        chunks = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        scores = []
        for chunk in chunks:
            with open(os.path.join(self.output_dir, chunk), 'r') as f:
                content = f.read()
                if 'RELEVANCE_SCORE:' in content:
                    score_line = [l for l in content.split('\n') if 'RELEVANCE_SCORE:' in l][0]
                    scores.append(float(score_line.split(':')[1].strip()))
        
        self.assertTrue(any(s > 0.5 for s in scores), "Should have some high relevance chunks")

    def test_api_key_redaction(self):
        """Test if API keys are properly redacted in the output chunks"""
        api_key_file = os.path.join(self.test_dir, "api_key_test.py")
        with open(api_key_file, "w", encoding="utf-8") as f:
            f.write('''
    API_KEY = "sk-abc123def456ghi789jkl"
    SECRET_KEY = "xyz9876543210abcdefghijk"
    normal_variable = "shortstring"
    def some_function():
        pass
            ''')

        chunker = EnhancedParallelChunker(
            equal_chunks=1,
            output_dir=self.output_dir,
            extract_metadata=True
        )
        chunker.process_directory(self.test_dir)

        chunk_files = [f for f in os.listdir(self.output_dir) if f.startswith('chunk-')]
        self.assertEqual(len(chunk_files), 1, "Expected exactly one chunk file")

        with open(os.path.join(self.output_dir, chunk_files[0]), 'r') as f:
            content = f.read()

        self.assertIn('[API_KEY_REDACTED]', content, "API keys should be redacted")
        self.assertNotIn('sk-abc123def456ghi789jkl', content, "Original API key should not appear")
        self.assertNotIn('xyz9876543210abcdefghijk', content, "Original secret key should not appear")
        self.assertIn('normal_variable = "shortstring"', content, "Non-API key content should remain unchanged")
        self.assertIn('some_function', content, "Function metadata should still be present")

if __name__ == '__main__':
    unittest.main()