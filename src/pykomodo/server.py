from flask import Flask, render_template, request, jsonify
import os
from pykomodo.multi_dirs_chunker import ParallelChunker
import concurrent.futures
import types

app = Flask(__name__, template_folder='template')

def scan_directory(root_dir, max_depth=3):
    files = []
    if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
        return files
    print(files)
    
    def scan_recursive(current_dir, current_depth=0):
        if current_depth > max_depth:
            return
        try:
            items = sorted(os.listdir(current_dir))
        except PermissionError:
            return
        
        for item in items:
            if item.startswith('.') or item in ['__pycache__', 'node_modules', '.git']:
                continue
            
            item_path = os.path.join(current_dir, item)
            if os.path.isfile(item_path):
                if not item.endswith(('.pyc', '.pyo')):
                    rel_path = os.path.relpath(item_path, root_dir)
                    files.append({
                        'name': rel_path,
                        'path': item_path,
                        'size': os.path.getsize(item_path)
                    })
            elif os.path.isdir(item_path):
                scan_recursive(item_path, current_depth + 1)
    
    scan_recursive(root_dir)
    return files

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/scan-directory', methods=['POST'])
def api_scan_directory():
    try:
        data = request.get_json()
        path = data.get('path', '.')
        
        if not os.path.exists(path):
            return jsonify({'success': False, 'error': f'Path does not exist: {path}'})
        
        if not os.path.isdir(path):
            return jsonify({'success': False, 'error': f'Path is not a directory: {path}'})
        
        files = scan_directory(path)
        
        return jsonify({
            'success': True,
            'files': files,
            'total': len(files)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/process-files', methods=['POST'])
def api_process_files():
    try:
        data = request.get_json()
        files = data.get('files', [])
        strategy = data.get('strategy', 'equal')
        num_chunks = data.get('numChunks', 5)
        chunk_size = data.get('chunkSize', 1000)
        output_dir = data.get('outputDir', 'chunks')
        
        if not files:
            return jsonify({'success': False, 'error': 'No files selected'})
        
        if strategy == 'equal':
            chunker = ParallelChunker(
                equal_chunks=int(num_chunks),
                output_dir=output_dir
            )
        else:
            chunker = ParallelChunker(
                max_chunk_size=int(chunk_size),
                output_dir=output_dir
            )
        
        def process_files(self, file_paths):
            if file_paths:
                first_file_dir = os.path.dirname(os.path.abspath(file_paths[0]))
                self.current_walk_root = first_file_dir
                self.tree_generator.reset()
            
            self.loaded_files.clear()
            valid_files = []
            for fp in file_paths:
                if os.path.isfile(fp):
                    valid_files.append(fp)

            if not valid_files:
                raise ValueError("No files found to process")
            
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads or 4)
            futures = []

            for path in valid_files:
                future = executor.submit(self._load_file_data, path)
                futures.append((future, path))

            for future, path in futures:
                try:
                    path, content, priority = future.result()
                    if content and not self.is_binary_file(path):
                        self.loaded_files.append((path, content, priority))
                except Exception as e:
                    print(f"Error processing {path}: {e}")

            if not self.loaded_files:
                raise ValueError("No files could be processed")
            
            self.loaded_files.sort(key=lambda f: f[2], reverse=True)
            self.loaded_files.sort(key=lambda f: f[0]) 

            self._process_chunks()
        
        chunker.process_files = types.MethodType(process_files, chunker)
        
        chunker.process_files(files)
        
        output_files = []
        if os.path.exists(output_dir):
            output_files = [f for f in os.listdir(output_dir) if f.endswith('.txt')]
        
        return jsonify({
            'success': True,
            'chunks': len(output_files),
            'output_dir': output_dir
        })
        
    except Exception as e:
        print(f"Error processing files: {e}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5555)