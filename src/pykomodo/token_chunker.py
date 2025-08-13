import os
import ast
import fitz  
import re
import tiktoken
from pykomodo.multi_dirs_chunker import ParallelChunker

class TokenBasedChunker(ParallelChunker):
    def __init__(
        self,
        equal_chunks = None,
        max_tokens_per_chunk = None,
        output_dir = "chunks",
        user_ignore = None,
        user_unignore = None,
        binary_extensions = None,
        priority_rules = None,
        num_threads = 4,
        dry_run = False,
        semantic_chunking = False,
        file_type = None,
        encoding_name = "cl100k_base",  
        verbose = False
    ):
        super().__init__(
            equal_chunks=equal_chunks,
            max_chunk_size=max_tokens_per_chunk, 
            output_dir=output_dir,
            user_ignore=user_ignore,
            user_unignore=user_unignore,
            binary_extensions=binary_extensions,
            priority_rules=priority_rules,
            num_threads=num_threads,
            dry_run=dry_run,
            semantic_chunking=semantic_chunking,
            file_type=file_type
        )
        
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.encoding_name = encoding_name
        self.verbose = verbose
        
        self.encoding = None
        try:
            self.encoding = tiktoken.get_encoding(encoding_name)
            if verbose:
                print(f"Using {encoding_name} tokenizer", flush=True)
        except Exception as e:
            print(f"Error initializing tokenizer: {e}. Falling back to word-splitting.")
    
    def count_tokens(self, text):
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            return len(text.split())
    
    def _chunk_by_equal_parts(self) -> None:
        if not self.loaded_files:
            return
        
        if self.verbose:
            print(f"Creating {self.equal_chunks} equal chunks based on token counts")
        
        chunks = [[] for _ in range(self.equal_chunks)]
        chunk_token_counts = [0] * self.equal_chunks
        
        text_blocks = []
        for path, content_bytes, priority in self.loaded_files:
            if path.endswith(".pdf"):
                try:
                    doc = fitz.open(path)
                    text = ""
                    for page in doc:
                        text += page.get_text("text")
                    token_count = self.count_tokens(text)
                    text_blocks.append((path, text, token_count))
                except:
                    if self.verbose:
                        print(f"Error extracting text from PDF {path}")
            else:
                try:
                    text = content_bytes.decode("utf-8", errors="replace")
                    text = self._filter_api_keys(text)
                    token_count = self.count_tokens(text)
                    text_blocks.append((path, text, token_count))
                except:
                    if self.verbose:
                        print(f"Error processing {path}")
        
        text_blocks.sort(key=lambda x: -x[2])
        
        for path, text, tokens in text_blocks:
            min_idx = chunk_token_counts.index(min(chunk_token_counts))
            chunks[min_idx].append((path, text))
            chunk_token_counts[min_idx] += tokens
        
        for i, chunk_files in enumerate(chunks):
            if not chunk_files:
                continue
            
            tree_header = ""
            if i == 0 and hasattr(self, 'current_walk_root') and self.current_walk_root:
                tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

            chunk_text = tree_header + f"{'=' * 80}\nCHUNK {i + 1} OF {self.equal_chunks}\n{'=' * 80}\n\n"

            for path, text in chunk_files:
                chunk_text += f"{'=' * 40}\nFile: {path}\n{'=' * 40}\n{text}\n\n"
            
            chunk_path = os.path.join(self.output_dir, f"chunk-{i}.txt")
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(chunk_text)
            
            if self.verbose:
                print(f"Created chunk {i+1} with approximately {chunk_token_counts[i]} tokens")
    
    def _chunk_by_size(self):
        if not self.loaded_files:
            return
        
        if self.verbose:
            print(f"Creating chunks with maximum {self.max_tokens_per_chunk} tokens per chunk")
        
        chunk_index = 0
        
        for path, content_bytes, _ in self.loaded_files:
            if path.endswith(".pdf"):
                chunk_index = self._chunk_pdf_file(path, chunk_index)
                continue
            
            if self.semantic_chunking and path.endswith(".py"):
                text = content_bytes.decode("utf-8", errors="replace")
                text = self._filter_api_keys(text)
                chunk_index = self._chunk_python_file_semantic(path, text, chunk_index)
                continue
            
            try:
                text = content_bytes.decode("utf-8", errors="replace")
                text = self._filter_api_keys(text)
            except Exception as e:
                if self.verbose:
                    print(f"Error decoding {path}: {e}")
                continue
            
            lines = text.splitlines()
            current_chunk_lines = []
            current_tokens = 0
            
            for line in lines:
                line_tokens = self.count_tokens(line)
                
                if current_tokens + line_tokens > self.max_tokens_per_chunk and current_chunk_lines:
                    tree_header = ""
                    if chunk_index == 0 and hasattr(self, 'current_walk_root') and self.current_walk_root:
                        tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

                    chunk_text = tree_header + f"{'=' * 80}\nCHUNK {chunk_index + 1}\n{'=' * 80}\n\n"
                    chunk_text += f"{'=' * 40}\nFile: {path}\n{'=' * 40}\n"
                    chunk_text += "\n".join(current_chunk_lines) + "\n"
                    
                    chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                    with open(chunk_path, "w", encoding="utf-8") as f:
                        f.write(chunk_text)
                    
                    chunk_index += 1
                    current_chunk_lines = []
                    current_tokens = 0
                
                if line_tokens > self.max_tokens_per_chunk:
                    if self.verbose:
                        print(f"Warning: Line in {path} exceeds token limit ({line_tokens} tokens)")
                    
                    if current_chunk_lines:
                        tree_header = ""
                        if hasattr(self, 'current_walk_root') and self.current_walk_root:
                            tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

                        chunk_text = tree_header + f"{'=' * 80}\nCHUNK {chunk_index + 1}\n{'=' * 80}\n\n"

                        chunk_text += f"{'=' * 40}\nFile: {path}\n{'=' * 40}\n"
                        chunk_text += "\n".join(current_chunk_lines) + "\n"
                        
                        chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                        with open(chunk_path, "w", encoding="utf-8") as f:
                            f.write(chunk_text)
                        
                        chunk_index += 1
                        current_chunk_lines = []
                        current_tokens = 0
                    
                    words = line.split()
                    word_chunks = []
                    current_word_chunk = []
                    current_word_tokens = 0
                    
                    for word in words:
                        word_tokens = self.count_tokens(word + ' ')
                        if current_word_tokens + word_tokens > self.max_tokens_per_chunk:
                            word_chunks.append(' '.join(current_word_chunk))
                            current_word_chunk = [word]
                            current_word_tokens = word_tokens
                        else:
                            current_word_chunk.append(word)
                            current_word_tokens += word_tokens
                    
                    if current_word_chunk:
                        word_chunks.append(' '.join(current_word_chunk))
                    
                    for i, word_chunk in enumerate(word_chunks):
                        tree_header = ""
                        if hasattr(self, 'current_walk_root') and self.current_walk_root:
                            tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

                        chunk_text = tree_header + f"{'=' * 80}\nCHUNK {chunk_index + 1}\n{'=' * 80}\n\n"

                        chunk_text += f"{'=' * 40}\nFile: {path}\n{'=' * 40}\n"
                        chunk_text += f"[Long line part {i+1}/{len(word_chunks)}]\n{word_chunk}\n"
                        
                        chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                        with open(chunk_path, "w", encoding="utf-8") as f:
                            f.write(chunk_text)
                        
                        chunk_index += 1
                    
                    continue
                
                if line.strip():
                    current_chunk_lines.append(line)
                    current_tokens += line_tokens
            
            if current_chunk_lines:
                tree_header = ""
                if hasattr(self, 'current_walk_root') and self.current_walk_root:
                    tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

                chunk_text = tree_header + f"{'=' * 80}\nCHUNK {chunk_index + 1}\n{'=' * 80}\n\n"

                chunk_text += f"{'=' * 40}\nFile: {path}\n{'=' * 40}\n"
                chunk_text += "\n".join(current_chunk_lines) + "\n"
                
                chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(chunk_text)
                
                chunk_index += 1
    
    def _chunk_python_file_semantic(self, path, text, chunk_index):
        try:
            tree = ast.parse(text, filename=path)
        except SyntaxError:
            if self.verbose:
                print(f"Syntax error in {path}, falling back to token-based chunking")
            
            lines = text.splitlines()
            current_chunk_lines = []
            current_tokens = 0
            
            for line in lines:
                line_tokens = self.count_tokens(line)
                
                if current_tokens + line_tokens > self.max_tokens_per_chunk and current_chunk_lines:
                    tree_header = ""
                    if hasattr(self, 'current_walk_root') and self.current_walk_root:
                        tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

                    chunk_text = tree_header + f"{'=' * 80}\nCHUNK {chunk_index + 1}\n{'=' * 80}\n\n"

                    chunk_text += f"{'=' * 40}\nFile: {path}\n{'=' * 40}\n"
                    chunk_text += "\n".join(current_chunk_lines) + "\n"
                    
                    chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                    with open(chunk_path, "w", encoding="utf-8") as f:
                        f.write(chunk_text)
                    
                    chunk_index += 1
                    current_chunk_lines = []
                    current_tokens = 0
                
                current_chunk_lines.append(line)
                current_tokens += line_tokens
            
            if current_chunk_lines:
                tree_header = ""
                if chunk_index == 0 and hasattr(self, 'current_walk_root') and self.current_walk_root:
                    tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

                chunk_text = tree_header + f"{'=' * 80}\nCHUNK {chunk_index + 1}\n{'=' * 80}\n\n"

                chunk_text += f"{'=' * 40}\nFile: {path}\n{'=' * 40}\n"
                chunk_text += "\n".join(current_chunk_lines) + "\n"
                
                chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(chunk_text)
                
                chunk_index += 1
            
            return chunk_index
        
        nodes = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start_line = node.lineno
                end_line = getattr(node, 'end_lineno', start_line)
                
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    node_type = "Function"
                    name = node.name
                else:
                    node_type = "Class"
                    name = node.name
                
                nodes.append({
                    'type': node_type,
                    'name': name,
                    'start': start_line,
                    'end': end_line
                })
        
        nodes.sort(key=lambda x: x['start'])
        
        lines = text.splitlines()
        line_ranges = []
        prev_end = 0
        
        for node in nodes:
            if node['start'] > prev_end + 1:
                line_ranges.append({
                    'type': 'Global',
                    'name': 'Code',
                    'start': prev_end + 1,
                    'end': node['start'] - 1
                })
            line_ranges.append(node)
            prev_end = node['end']
        
        if prev_end < len(lines):
            line_ranges.append({
                'type': 'Global',
                'name': 'Code',
                'start': prev_end + 1,
                'end': len(lines)
            })
        
        current_chunk_blocks = []
        current_tokens = 0
        
        for block in line_ranges:
            block_lines = lines[block['start']-1:block['end']]
            block_text = f"{block['type']}: {block['name']} (lines {block['start']}-{block['end']})\n"
            block_text += "\n".join(block_lines)
            
            block_tokens = self.count_tokens(block_text)
            
            if block_tokens > self.max_tokens_per_chunk:
                if self.verbose:
                    print(f"Warning: {block['type']} {block['name']} in {path} exceeds token limit ({block_tokens} tokens)")
                
                if current_chunk_blocks:

                    tree_header = ""
                    if hasattr(self, 'current_walk_root') and self.current_walk_root:
                        tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

                    chunk_text = tree_header + f"{'=' * 80}\nFILE: {path}\n{'=' * 80}\n\n"

                    chunk_text += "\n\n".join(current_chunk_blocks)
                    
                    chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                    with open(chunk_path, "w", encoding="utf-8") as f:
                        f.write(chunk_text)
                    
                    chunk_index += 1
                    current_chunk_blocks = []
                    current_tokens = 0
                
                chunk_text = tree_header + f"{'=' * 80}\nFILE: {path}\n{'=' * 80}\n\n{block_text}"                
                chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(chunk_text)
                
                chunk_index += 1
                continue
            
            tree_header = ""
            if hasattr(self, 'current_walk_root') and self.current_walk_root:
                tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

            if current_tokens + block_tokens > self.max_tokens_per_chunk and current_chunk_blocks:
                chunk_text = tree_header + f"{'=' * 80}\nFILE: {path}\n{'=' * 80}\n\n"
                chunk_text += "\n\n".join(current_chunk_blocks)
                
                chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(chunk_text)
                
                chunk_index += 1
                current_chunk_blocks = []
                current_tokens = 0
            
            current_chunk_blocks.append(block_text)
            current_tokens += block_tokens
        
        tree_header = ""
        if hasattr(self, 'current_walk_root') and self.current_walk_root:
            tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)
            
        if current_chunk_blocks:
            chunk_text = tree_header + f"{'=' * 80}\nFILE: {path}\n{'=' * 80}\n\n"
            chunk_text += "\n\n".join(current_chunk_blocks)
            
            chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(chunk_text)
            
            chunk_index += 1
        
        return chunk_index
    
    def _chunk_pdf_file(self, path, chunk_index):
        try:
            doc = fitz.open(path)
            
            all_paragraphs = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                
                try:
                    html = page.get_text("html")
                    if "<p>" in html:
                        paragraphs = re.findall(r'<p>(.*?)</p>', html, re.DOTALL)
                        clean_paras = []
                        
                        for p in paragraphs:
                            clean_p = re.sub(r'<.*?>', ' ', p)
                            clean_p = re.sub(r'&[a-zA-Z]+;', ' ', clean_p)
                            clean_p = re.sub(r'\s+', ' ', clean_p).strip()
                            
                            if clean_p:
                                clean_paras.append(clean_p)
                        
                        all_paragraphs.append(f"--- Page {page_num + 1} ---")
                        all_paragraphs.extend(clean_paras)
                        continue
                except Exception:
                    pass
                
                page_paragraphs = text.split("\n\n")
                
                all_paragraphs.append(f"--- Page {page_num + 1} ---")
                
                for para in page_paragraphs:
                    if para.strip():
                        all_paragraphs.append(para.strip())
            
            current_chunk_paras = []
            current_tokens = 0
            
            for para in all_paragraphs:
                para_tokens = self.count_tokens(para)
                
                if para_tokens == 0:
                    continue
                
                if current_tokens + para_tokens > self.max_tokens_per_chunk and current_chunk_paras:
                    tree_header = ""
                    if hasattr(self, 'current_walk_root') and self.current_walk_root:
                        tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

                    chunk_text = tree_header + f"{'=' * 80}\nFILE: {path}\n{'=' * 80}\n\n"
                    chunk_text += "\n\n".join(current_chunk_paras)
                    
                    chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                    with open(chunk_path, "w", encoding="utf-8") as f:
                        f.write(chunk_text)
                    
                    chunk_index += 1
                    current_chunk_paras = []
                    current_tokens = 0
                
                current_chunk_paras.append(para)
                current_tokens += para_tokens
            
            tree_header = ""
            if chunk_index == 0 and hasattr(self, 'current_walk_root') and self.current_walk_root:
                tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)

            if current_chunk_paras:
                chunk_text = tree_header + f"{'=' * 80}\nFILE: {path}\n{'=' * 80}\n\n"
                chunk_text += "\n\n".join(current_chunk_paras)
                
                chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(chunk_text)
                
                chunk_index += 1
            
            return chunk_index
            
        except Exception as e:
            if self.verbose:
                print(f"Error processing PDF {path}: {e}")

            chunk_text = tree_header + f"{'=' * 80}\nFILE: {path}\n{'=' * 80}\n\n"
            chunk_text += f"[Error processing PDF: {str(e)}]\n"
            
            chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_index}.txt")
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(chunk_text)
            
            return chunk_index + 1