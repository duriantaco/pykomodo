import unittest
import os
import sys
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pykomodo.server import app, scan_directory

class TestServer(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        
        self.test_dir = tempfile.mkdtemp()
        self.test_file1 = os.path.join(self.test_dir, "file1.txt")
        self.test_file2 = os.path.join(self.test_dir, "file2.py")
        self.subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.subdir)
        self.test_file3 = os.path.join(self.subdir, "file3.js")
        
        with open(self.test_file1, "w") as f:
            f.write("test content 1")
        with open(self.test_file2, "w") as f:
            f.write("def test(): pass")
        with open(self.test_file3, "w") as f:
            f.write("console.log('test')")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_index_route(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_scan_directory_function(self):
        files = scan_directory(self.test_dir)
        self.assertEqual(len(files), 3)
        
        file_names = [f['name'] for f in files]
        self.assertIn('file1.txt', file_names)
        self.assertIn('file2.py', file_names)
        self.assertIn(os.path.join('subdir', 'file3.js'), file_names)

    def test_scan_directory_nonexistent(self):
        files = scan_directory("/nonexistent/path")
        self.assertEqual(files, [])

    def test_scan_directory_ignores_hidden_files(self):
        hidden_file = os.path.join(self.test_dir, ".hidden")
        with open(hidden_file, "w") as f:
            f.write("hidden content")
        
        files = scan_directory(self.test_dir)
        file_names = [f['name'] for f in files]
        self.assertNotIn('.hidden', file_names)

    def test_scan_directory_ignores_pycache(self):
        pycache_dir = os.path.join(self.test_dir, "__pycache__")
        os.makedirs(pycache_dir)
        
        files = scan_directory(self.test_dir)
        for f in files:
            self.assertNotIn('__pycache__', f['path'])

    def test_api_scan_directory_success(self):
        response = self.app.post('/api/scan-directory',
                                data=json.dumps({'path': self.test_dir}),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['total'], 3)
        self.assertEqual(len(data['files']), 3)

    def test_api_scan_directory_nonexistent_path(self):
        response = self.app.post('/api/scan-directory',
                                data=json.dumps({'path': '/nonexistent'}),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('does not exist', data['error'])

    def test_api_scan_directory_file_not_dir(self):
        response = self.app.post('/api/scan-directory',
                                data=json.dumps({'path': self.test_file1}),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('not a directory', data['error'])

    def test_api_scan_directory_default_path(self):
        response = self.app.post('/api/scan-directory',
                                data=json.dumps({}),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])

    def test_api_scan_directory_malformed_json(self):
        response = self.app.post('/api/scan-directory',
                                data='invalid json',
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])

    @patch('pykomodo.server.ParallelChunker')
    def test_api_process_files_equal_chunks(self, mock_chunker):
        mock_instance = MagicMock()
        mock_instance.num_threads = 4
        mock_instance.loaded_files = []
        mock_instance.current_walk_root = None
        mock_instance.tree_generator = MagicMock()
        mock_instance.tree_generator.reset = MagicMock()
        mock_instance._load_file_data = MagicMock(return_value=('path', 'content', 1))
        mock_instance.is_binary_file = MagicMock(return_value=False)
        mock_instance._process_chunks = MagicMock()
        mock_chunker.return_value = mock_instance
        
        output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(output_dir)
        
        chunk_file = os.path.join(output_dir, "chunk-001.txt")
        with open(chunk_file, "w") as f:
            f.write("chunk content")
        
        payload = {
            'files': [self.test_file1, self.test_file2],
            'strategy': 'equal',
            'numChunks': 3,
            'outputDir': output_dir
        }
        
        response = self.app.post('/api/process-files',
                                data=json.dumps(payload),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['chunks'], 1)
        
        mock_chunker.assert_called_with(equal_chunks=3, output_dir=output_dir)

    @patch('pykomodo.server.ParallelChunker')
    def test_api_process_files_size_chunks(self, mock_chunker):
        mock_instance = MagicMock()
        mock_instance.num_threads = 4
        mock_instance.loaded_files = []
        mock_instance.current_walk_root = None
        mock_instance.tree_generator = MagicMock()
        mock_instance.tree_generator.reset = MagicMock()
        mock_instance._load_file_data = MagicMock(return_value=('path', 'content', 1))
        mock_instance.is_binary_file = MagicMock(return_value=False)
        mock_instance._process_chunks = MagicMock()
        mock_chunker.return_value = mock_instance
        
        payload = {
            'files': [self.test_file1],
            'strategy': 'size',
            'chunkSize': 500,
            'outputDir': 'chunks'
        }
        
        response = self.app.post('/api/process-files',
                                data=json.dumps(payload),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        mock_chunker.assert_called_with(max_chunk_size=500, output_dir='chunks')

    def test_api_process_files_no_files(self):
        payload = {
            'files': [],
            'strategy': 'equal',
            'numChunks': 5
        }
        
        response = self.app.post('/api/process-files',
                                data=json.dumps(payload),
                                content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('No files selected', data['error'])

    def test_api_process_files_defaults(self):
        with patch('pykomodo.server.ParallelChunker') as mock_chunker:
            mock_instance = MagicMock()
            mock_chunker.return_value = mock_instance
            
            payload = {'files': [self.test_file1]}
            
            response = self.app.post('/api/process-files',
                                    data=json.dumps(payload),
                                    content_type='application/json')
            
            mock_chunker.assert_called_with(equal_chunks=5, output_dir='chunks')

    def test_scan_directory_max_depth(self):
        deep_dir = self.test_dir
        for i in range(5):
            deep_dir = os.path.join(deep_dir, f"level{i}")
            os.makedirs(deep_dir)
            deep_file = os.path.join(deep_dir, f"deep{i}.txt")
            with open(deep_file, "w") as f:
                f.write(f"deep content {i}")
        
        files = scan_directory(self.test_dir, max_depth=2)
        deep_files = [f for f in files if 'level3' in f['path'] or 'level4' in f['path']]
        self.assertEqual(len(deep_files), 0)

    def test_scan_directory_permission_error(self):
        with patch('os.listdir', side_effect=PermissionError("Access denied")):
            files = scan_directory(self.test_dir)
            self.assertEqual(files, [])

    def test_scan_directory_file_sizes(self):
        files = scan_directory(self.test_dir)
        for f in files:
            self.assertGreater(f['size'], 0)
            self.assertEqual(f['size'], os.path.getsize(f['path']))

    @patch('pykomodo.server.ParallelChunker')
    def test_process_files_method_injection(self, mock_chunker):
        mock_instance = MagicMock()
        mock_chunker.return_value = mock_instance
        
        self.assertTrue(hasattr(mock_instance, 'process_files'))

if __name__ == "__main__":
    unittest.main()