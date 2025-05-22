import gradio as gr
import os
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
    
    custom_css = """
    .gradio-container {
        max-width: 1200px !important;
        margin: 0 auto !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }
    
    .header {
        text-align: center;
        padding: 30px 0;
        border-bottom: 2px solid #e5e7eb;
        margin-bottom: 30px;
    }
    
    .header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f2937;
        margin: 0;
    }
    
    .header p {
        font-size: 1.1rem;
        color: #6b7280;
        margin: 10px 0 0 0;
    }
    
    .step-section {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }
    
    .step-header {
        display: flex;
        align-items: center;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid #f3f4f6;
    }
    
    .step-number {
        background: #1f2937;
        color: white;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        margin-right: 16px;
        font-size: 14px;
    }
    
    .step-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1f2937;
        margin: 0;
    }
    
    .instructions {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 16px;
        margin-bottom: 24px;
    }
    
    .instructions h3 {
        margin: 0 0 12px 0;
        color: #1e293b;
        font-size: 1rem;
        font-weight: 600;
    }
    
    .instructions ol {
        margin: 0;
        padding-left: 20px;
        color: #475569;
    }
    
    .instructions li {
        margin-bottom: 4px;
    }
    
    .config-panel {
        background: #fafafa;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 24px;
    }
    
    .config-header {
        text-align: center;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid #e5e7eb;
    }
    
    .config-header h2 {
        margin: 0;
        color: #1f2937;
        font-size: 1.5rem;
        font-weight: 600;
    }
    
    .gr-button {
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
    }
    
    .gr-button-primary {
        background: #1f2937 !important;
        border: 1px solid #1f2937 !important;
    }
    
    .gr-button-primary:hover {
        background: #111827 !important;
        border: 1px solid #111827 !important;
    }
    
    .gr-button-secondary {
        background: white !important;
        border: 1px solid #d1d5db !important;
        color: #374151 !important;
    }
    
    .gr-button-secondary:hover {
        background: #f9fafb !important;
        border: 1px solid #9ca3af !important;
    }
    
    .gr-textbox, .gr-dropdown {
        border-radius: 6px !important;
        border: 1px solid #d1d5db !important;
    }
    
    .gr-textbox:focus, .gr-dropdown:focus {
        border-color: #1f2937 !important;
        box-shadow: 0 0 0 3px rgba(31, 41, 55, 0.1) !important;
    }
    
    .status-display {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        padding: 16px;
        font-family: 'SF Mono', Monaco, monospace;
        font-size: 13px;
        line-height: 1.5;
    }
    
    .file-selection {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        padding: 16px;
        min-height: 200px;
    }
    
    .selection-summary {
        background: #f9fafb;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        padding: 16px;
        margin-top: 16px;
    }
    
    .selection-summary h4 {
        margin: 0 0 8px 0;
        color: #374151;
        font-size: 14px;
        font-weight: 600;
    }
    """
    
    with gr.Blocks(
        theme=gr.themes.Default(),
        css=custom_css,
        title="Komodo Chunking Tool"
    ) as demo:
        
        gr.HTML("""
            <div class="header">
                <h1>Komodo Chunking Tool</h1>
                <p>Professional code file processing and chunking</p>
            </div>
        """)
        
        gr.HTML("""
            <div class="instructions">
                <h3>How to use this tool:</h3>
                <ol>
                    <li>Enter your repository path and click "Load Repository"</li>
                    <li>Select a folder from the dropdown to view its files</li>
                    <li>Check the files you want to process</li>
                    <li>Configure chunking settings and click "Process Files"</li>
                </ol>
            </div>
        """)
        
        current_folder = gr.State(value="")
        all_files_data = gr.State(value={})
        all_selected_files = gr.State(value=[])
        
        with gr.Row():
            
            with gr.Column(scale=2):
                
                gr.HTML("""
                    <div class="step-section">
                        <div class="step-header">
                            <div class="step-number">1</div>
                            <h3 class="step-title">Load Repository</h3>
                        </div>
                """)
                
                repo_path = gr.Textbox(
                    label="Repository Path",
                    placeholder="Enter path to your code repository (e.g., /Users/yourname/project or .)",
                    value=".",
                    info="Path to the directory containing your code files"
                )
                
                load_btn = gr.Button("Load Repository", variant="primary", size="lg")
                
                load_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    value="Enter repository path and click 'Load Repository' to begin",
                    elem_classes="status-display"
                )
                
                gr.HTML("</div>")

                ## step2 -> select folder
                gr.HTML("""
                    <div class="step-section">
                        <div class="step-header">
                            <div class="step-number">2</div>
                            <h3 class="step-title">Select Folder</h3>
                        </div>
                """)
                
                folder_dropdown = gr.Dropdown(
                    label="Choose folder to explore",
                    choices=[],
                    value="",
                    info="Select a folder to view its files"
                )
                
                gr.HTML("</div>")
                
                # step3 -> file select
                gr.HTML("""
                    <div class="step-section">
                        <div class="step-header">
                            <div class="step-number">3</div>
                            <h3 class="step-title">Select Files</h3>
                        </div>
                """)
                
                file_checkboxes = gr.CheckboxGroup(
                    label="Files in selected folder",
                    choices=[],
                    value=[],
                    info="Check the files you want to process",
                    elem_classes="file-selection"
                )
                
                with gr.Row():
                    select_all_btn = gr.Button("Select All", size="sm", variant="secondary")
                    clear_selection_btn = gr.Button("Clear Selection", size="sm", variant="secondary")
                
                gr.HTML("</div>")
                
                gr.HTML("""
                    <div class="selection-summary">
                        <h4>Selected Files Summary</h4>
                """)
                
                selected_display = gr.Textbox(
                    label="Currently selected files",
                    interactive=False,
                    lines=4,
                    value="No files selected",
                    show_label=False
                )
                
                gr.HTML("</div>")
            
            with gr.Column(scale=1):
                
                gr.HTML("""
                    <div class="config-panel">
                        <div class="config-header">
                            <h2>Configuration</h2>
                        </div>
                """)
                
                strategy = gr.Dropdown(
                    label="Chunking Strategy",
                    choices=["Equal Chunks", "Max Chunk Size"], 
                    value="Equal Chunks",
                    info="How to split your files"
                )
                
                num_chunks = gr.Number(
                    label="Number of Chunks", 
                    value=5, 
                    minimum=1, 
                    step=1,
                    visible=True,
                    info="Split files into this many equal parts"
                )
                
                max_chunk_size = gr.Number(
                    label="Max Chunk Size (tokens)", 
                    value=1000, 
                    minimum=100, 
                    step=100,
                    visible=False,
                    info="Maximum size for each chunk"
                )
                
                output_dir = gr.Textbox(
                    label="Output Directory", 
                    value="chunks",
                    placeholder="Directory to save chunks",
                    info="Where to save the processed files"
                )
                
                process_btn = gr.Button("Process Files", variant="primary", size="lg")
                
                status = gr.Textbox(
                    label="Processing Status",
                    interactive=False, 
                    lines=6,
                    value="Ready to process files",
                    elem_classes="status-display"
                )
                
                gr.HTML("</div>")
        
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