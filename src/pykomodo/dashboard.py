import gradio as gr
import os
import json
import concurrent.futures
import types

def get_files_by_folder(root_dir, max_depth=3):
    files_by_folder = {}
    if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
        return files_by_folder
    
    def scan_directory(current_dir, current_depth=0):
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
                    folder = os.path.relpath(os.path.dirname(item_path), root_dir)
                    if folder == '.':
                        folder = 'Root Directory'
                    if folder not in files_by_folder:
                        files_by_folder[folder] = []
                    files_by_folder[folder].append((item, item_path))
            elif os.path.isdir(item_path):
                scan_directory(item_path, current_depth + 1)
    
    scan_directory(root_dir)
    return files_by_folder

def process_chunks(strategy, num_chunks, max_chunk_size, output_dir, selected_files):
    try:
        
        if not selected_files:
            return "❌ No files selected. Please select files using the checkboxes."
        
        try:
            from pykomodo.multi_dirs_chunker import ParallelChunker
        except ImportError as e:
            return f"❌ Error: Could not import ParallelChunker. Make sure pykomodo is installed.\nError: {e}"
        
        if not output_dir.strip():
            return "❌ Please provide an output directory."
        
        output_dir = output_dir.strip()
        os.makedirs(output_dir, exist_ok=True)
        
        if strategy == "Equal Chunks":
            if not num_chunks or num_chunks <= 0:
                return "❌ Please provide a positive number of chunks."
            chunker = ParallelChunker(equal_chunks=int(num_chunks), output_dir=output_dir)
        elif strategy == "Max Chunk Size":
            if not max_chunk_size or max_chunk_size <= 0:
                return "❌ Please provide a positive max chunk size."
            chunker = ParallelChunker(max_chunk_size=int(max_chunk_size), output_dir=output_dir)
        else:
            return "❌ Invalid chunking strategy selected."
        
        if not hasattr(chunker, 'process_files'):
            def process_files(self, file_paths):
                self.loaded_files.clear()
                valid_files = [fp for fp in file_paths if os.path.isfile(fp)]
                if not valid_files:
                    raise ValueError("No valid files found to process")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=getattr(self, 'num_threads', 4)) as ex:
                    future_map = {ex.submit(self._load_file_data, p): p for p in valid_files}
                    for fut in concurrent.futures.as_completed(future_map):
                        try:
                            path, content, priority = fut.result()
                            if content is not None and not self.is_binary_file(path):
                                self.loaded_files.append((path, content, priority))
                        except Exception as e:
                            print(f"Error processing file: {e}")
                
                if not self.loaded_files:
                    raise ValueError("No files could be processed")
                
                self.loaded_files.sort(key=lambda x: (-x[2], x[0]))
                self._process_chunks()
            
            chunker.process_files = types.MethodType(process_files, chunker)
        
        chunker.process_files(selected_files)
        
        output_files = []
        if os.path.exists(output_dir):
            output_files = [f for f in os.listdir(output_dir) if f.endswith('.txt')]
        
        return f"✅ Chunking completed successfully!\n📁 Output directory: {output_dir}\n📄 Files processed: {len(selected_files)}\n📦 Chunks created: {len(output_files)}"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error during processing: {str(e)}"

def launch_dashboard():
    
    with gr.Blocks(theme=gr.themes.Soft(), title="Komodo Chunking Tool") as demo:
        
        gr.Markdown("""
        # 🦎 Komodo Chunking Tool
        ### No hassle chunking for your code files!
        """)
        
        current_folder = gr.State(value="")
        all_files_data = gr.State(value={})
        
        with gr.Row():
            with gr.Column(scale=3):
                gr.Markdown("### 📁 Repository Selection")
                repo_path = gr.Textbox(
                    label="Repository Path", 
                    placeholder="Enter path (e.g., /path/to/repo or .)",
                    value=".",
                    info="Path to your code repository"
                )
                
                load_btn = gr.Button("🔄 Load Files", variant="primary")
                
                gr.Markdown("### 📂 Select Folder to View")
                folder_dropdown = gr.Dropdown(
                    label="Choose Folder",
                    choices=[],
                    value="",
                    info="Select a folder to see its files"
                )
                
                gr.Markdown("### 📄 Files in Selected Folder")
                file_checkboxes = gr.CheckboxGroup(
                    label="Select Files to Process",
                    choices=[],
                    value=[],
                    info="Select files from the current folder"
                )
                
                with gr.Row():
                    select_all_btn = gr.Button("✅ Select All in Folder", size="sm")
                    clear_selection_btn = gr.Button("❌ Clear Selection", size="sm")
                
                gr.Markdown("### 📋 Currently Selected Files")
                selected_display = gr.Textbox(
                    label="Selected Files",
                    interactive=False,
                    lines=4,
                    value="No files selected"
                )
                
                load_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    value="Enter a repository path and click 'Load Files' to start..."
                )
            
            with gr.Column(scale=2):
                gr.Markdown("### ⚙️ Configuration")
                
                strategy = gr.Dropdown(
                    label="Chunking Strategy", 
                    choices=["Equal Chunks", "Max Chunk Size"], 
                    value="Equal Chunks"
                )
                
                num_chunks = gr.Number(
                    label="Number of Chunks", 
                    value=5, 
                    minimum=1, 
                    step=1,
                    visible=True
                )
                max_chunk_size = gr.Number(
                    label="Max Chunk Size (tokens)", 
                    value=1000, 
                    minimum=100, 
                    step=100,
                    visible=False
                )
                
                output_dir = gr.Textbox(
                    label="Output Directory", 
                    value="chunks",
                    placeholder="Directory to save chunks"
                )
                
                process_btn = gr.Button("🚀 Process Files", variant="primary", size="lg")
                
                status = gr.Textbox(
                    label="Processing Status", 
                    interactive=False, 
                    lines=4
                )
        
        all_selected_files = gr.State(value=[])
        
        def load_files(repo_path):
            try:
                if not repo_path or not repo_path.strip():
                    return (gr.update(choices=[], value=""), 
                            gr.update(choices=[], value=[]), 
                            {}, [], "No files selected",
                            "❌ Please enter a repository path")
                
                repo_path = repo_path.strip()
                
                if not os.path.exists(repo_path):
                    return (gr.update(choices=[], value=""), 
                            gr.update(choices=[], value=[]), 
                            {}, [], "No files selected",
                            f"❌ Path does not exist: {repo_path}")
                    
                if not os.path.isdir(repo_path):
                    return (gr.update(choices=[], value=""), 
                            gr.update(choices=[], value=[]), 
                            {}, [], "No files selected",
                            f"❌ Path is not a directory: {repo_path}")
                
                files_by_folder = get_files_by_folder(repo_path)
                
                if not files_by_folder:
                    return (gr.update(choices=[], value=""), 
                            gr.update(choices=[], value=[]), 
                            {}, [], "No files selected",
                            "❌ No files found in directory")
                
                total_files = sum(len(files) for files in files_by_folder.values())
                
                folder_choices = []
                for folder, files in sorted(files_by_folder.items()):
                    folder_choices.append(f"📁 {folder} ({len(files)} files)")
                
                first_folder = folder_choices[0] if folder_choices else ""
                first_folder_files = []
                if first_folder:
                    actual_folder = first_folder.split("📁 ")[1].split(" (")[0]
                    if actual_folder in files_by_folder:
                        first_folder_files = [(f"📄 {filename}", filepath) 
                                            for filename, filepath in files_by_folder[actual_folder]]
                
                status_msg = f"✅ Found {total_files} files in {len(files_by_folder)} folders"
                
                return (gr.update(choices=folder_choices, value=first_folder),
                        gr.update(choices=first_folder_files, value=[]),
                        files_by_folder, [], "No files selected", status_msg)
                
            except Exception as e:
                return (gr.update(choices=[], value=""), 
                        gr.update(choices=[], value=[]), 
                        {}, [], "No files selected", f"❌ Error: {str(e)}")
        
        def update_files_for_folder(selected_folder, files_data, current_selected):
            if not selected_folder or not files_data:
                return gr.update(choices=[], value=[]), current_selected, "No files selected"
            
            folder_name = selected_folder.split("📁 ")[1].split(" (")[0]
            
            if folder_name not in files_data:
                return gr.update(choices=[], value=[]), current_selected, "No files selected"
            
            file_choices = [(f"📄 {filename}", filepath) 
                           for filename, filepath in files_data[folder_name]]
            
            current_folder_files = [filepath for filename, filepath in files_data[folder_name]]
            kept_selections = [f for f in current_selected if f in current_folder_files]
            
            if current_selected:
                display_text = f"Selected {len(current_selected)} files:\n" + "\n".join([
                    os.path.basename(f) for f in current_selected
                ])
            else:
                display_text = "No files selected"
            
            return gr.update(choices=file_choices, value=kept_selections), current_selected, display_text
        
        def update_selected_files(folder_selections, current_all_selected):
            if not folder_selections:
                return current_all_selected, "No files selected"
            
            new_all_selected = list(set(current_all_selected + folder_selections))
            
            if new_all_selected:
                display_text = f"Selected {len(new_all_selected)} files:\n" + "\n".join([
                    os.path.basename(f) for f in new_all_selected
                ])
            else:
                display_text = "No files selected"
            
            return new_all_selected, display_text
        
        def select_all_in_folder(folder_selections):
            return folder_selections if folder_selections else []
        
        def clear_all_selections():
            return [], [], "No files selected"
        
        def update_visibility(strategy):
            if strategy == "Equal Chunks":
                return gr.update(visible=True), gr.update(visible=False)
            else:
                return gr.update(visible=False), gr.update(visible=True)
        
        def process_files_handler(strategy, num_chunks, max_chunk_size, output_dir, selected_files):
            return process_chunks(strategy, num_chunks, max_chunk_size, output_dir, selected_files)
        
        load_btn.click(
            load_files, 
            inputs=[repo_path], 
            outputs=[folder_dropdown, file_checkboxes, all_files_data, all_selected_files, selected_display, load_status]
        )
        
        folder_dropdown.change(
            update_files_for_folder,
            inputs=[folder_dropdown, all_files_data, all_selected_files],
            outputs=[file_checkboxes, all_selected_files, selected_display]
        )
        
        file_checkboxes.change(
            update_selected_files,
            inputs=[file_checkboxes, all_selected_files],
            outputs=[all_selected_files, selected_display]
        )
        
        select_all_btn.click(
            lambda choices: choices,
            inputs=[file_checkboxes],
            outputs=[file_checkboxes]
        )
        
        clear_selection_btn.click(
            clear_all_selections,
            outputs=[all_selected_files, file_checkboxes, selected_display]
        )
        
        strategy.change(
            update_visibility, 
            inputs=[strategy], 
            outputs=[num_chunks, max_chunk_size]
        )
        
        process_btn.click(
            process_files_handler,
            inputs=[strategy, num_chunks, max_chunk_size, output_dir, all_selected_files],
            outputs=[status]
        )
    
    return demo

if __name__ == "__main__":
    demo = launch_dashboard()
    demo.launch(debug=False)