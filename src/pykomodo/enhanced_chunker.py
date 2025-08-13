from pykomodo.multi_dirs_chunker import ParallelChunker
import os

class EnhancedParallelChunker(ParallelChunker):
    def __init__(
        self,
        equal_chunks = None,
        max_chunk_size = None,
        output_dir = "chunks",
        user_ignore = None,
        user_unignore = None,
        binary_extensions = None,
        priority_rules = None,
        num_threads = 4,
        extract_metadata = True,
        add_summaries = True,
        remove_redundancy = True,
        context_window = 4096,
        min_relevance_score = 0.3
    ):
        super().__init__(
            equal_chunks=equal_chunks,
            max_chunk_size=max_chunk_size,
            output_dir=output_dir,
            user_ignore=user_ignore,
            user_unignore=user_unignore,
            binary_extensions=binary_extensions,
            priority_rules=priority_rules,
            num_threads=num_threads
        )
        self.extract_metadata = extract_metadata
        self.add_summaries = add_summaries
        self.remove_redundancy = remove_redundancy
        self.context_window = context_window
        self.min_relevance_score = min_relevance_score

    def _extract_file_metadata(self, content):
        metadata = {
            "functions": [],
            "classes": [],
            "imports": [],
            "docstrings": []
        }
        
        lines = content.split('\n')
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith('def '):
                func_name = line_stripped[4:].split('(')[0].strip()
                if func_name != '__init__':  
                    metadata['functions'].append(func_name)

            elif line_stripped.startswith('class '):
                class_name = line_stripped[6:].split('(')[0].strip()
                class_name = class_name.rstrip(':')
                metadata['classes'].append(class_name)

            elif line_stripped.startswith('import '):
                if ' as ' in line_stripped:
                    base_import = line_stripped.split(' as ')[0].strip() 
                    metadata['imports'].append(base_import)
                else:
                    metadata['imports'].append(line_stripped)

            elif line_stripped.startswith('from '):
                base_from = line_stripped.split(' import ')[0].strip() 
                metadata['imports'].append(base_from)
                
        if '"""' in content:
            start = content.find('"""') + 3
            end = content.find('"""', start)

            if end > start:
                docstring = content[start:end].strip()
                metadata['docstrings'].append(docstring)
                
        return metadata

    def _calculate_chunk_relevance(self, chunk_content):
        all_lines = chunk_content.split('\n')
        lines = []
        for line in all_lines:
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
        
        if not lines:
            return 0.0
            
        code_lines = 0
        comment_lines = 0
        for line in lines:
            if line.startswith('#'):
                comment_lines += 1
            else:
                code_lines += 1

        if code_lines == 0:
            return 0.3  

        score = 1.0

        total_lines = code_lines + comment_lines
        if total_lines == 0:
            comment_ratio = 0.0
        else:
            comment_ratio = comment_lines / total_lines

        if comment_ratio > 0.5:
            score *= 0.8  

        return min(0.99, score)

    def _remove_redundancy_across_all_files(self, big_text):

        lines = big_text.split('\n')
        final_lines = []
        in_function = False
        current_function = []

        def normalize_function(func_text):
            lines_ = []
            for ln in func_text.split('\n'):
                lines_.append(ln.strip())
            
            filtered_lines = []
            for ln in lines_:
                if ln:
                    filtered_lines.append(ln)
            lines_ = filtered_lines

            return '\n'.join(lines_)

        seen_functions = {}

        for line in lines:
            stripped = line.rstrip()
            if stripped.strip().startswith('def '):
                if in_function and current_function:
                    normed = normalize_function('\n'.join(current_function))
                    if normed not in seen_functions:
                        seen_functions[normed] = True
                        final_lines.extend(current_function)
                current_function = [line]
                in_function = True
                
            elif in_function:
                if stripped.strip().startswith('def '):
                    normed = normalize_function('\n'.join(current_function))
                    if normed not in seen_functions:
                        seen_functions[normed] = True
                        final_lines.extend(current_function)
                    current_function = [line]
                else:
                    current_function.append(line)
            else:
                final_lines.append(line)

        if in_function and current_function:
            normed = normalize_function('\n'.join(current_function))
            if normed not in seen_functions:
                seen_functions[normed] = True
                final_lines.extend(current_function)

        return "\n".join(final_lines)

    def _chunk_by_equal_parts(self) -> None:
        if not self.loaded_files:
            return

        all_file_texts = []
        combined_metadata = {
            "functions": set(),
            "classes": set(),
            "imports": [],
            "docstrings": set()
        }

        for path, content_bytes, _ in self.loaded_files:
            try:
                content = content_bytes.decode('utf-8', errors='replace')
            except Exception:
                print(f"Error decoding file {path}")
                continue

            if self.extract_metadata:
                fm = self._extract_file_metadata(content)
                combined_metadata["functions"].update(fm["functions"])
                combined_metadata["classes"].update(fm["classes"])
                
                combined_metadata["imports"].extend(fm["imports"])  

                combined_metadata["docstrings"].update(fm["docstrings"])
            
            all_file_texts.append(content)

        combined_text = "\n".join(all_file_texts)
        if self.remove_redundancy:
            combined_text = self._remove_redundancy_across_all_files(combined_text)

        if not self.equal_chunks or self.equal_chunks <= 1:
            self._create_and_write_chunk(
                combined_text,
                0,
                combined_metadata if self.extract_metadata else None
            )
            return

        total_size = len(combined_text.encode('utf-8'))
        if self.context_window and self.context_window > 200:
            max_size = self.context_window - 50
            max_size = int(max_size)
        else:
            max_size = float('inf')
        target_size = min(total_size // self.equal_chunks, max_size)

        chunk_num = 0
        remaining = combined_text
        while remaining:
            portion_bytes = remaining.encode('utf-8')[:target_size]
            portion = portion_bytes.decode('utf-8', errors='replace')

            last_newline = portion.rfind('\n')
            if last_newline > 0:
                portion = portion[:last_newline]

            self._create_and_write_chunk(
                portion,
                chunk_num,
                combined_metadata if self.extract_metadata else None
            )
            chunk_num += 1

            portion_len = len(portion)
            remaining = remaining[portion_len:]

            if chunk_num >= self.equal_chunks - 1:
                if remaining:
                    self._create_and_write_chunk(
                        remaining,
                        chunk_num,
                        combined_metadata if self.extract_metadata else None
                    )
                break

    def _create_and_write_chunk(self, text, chunk_num, metadata = None):
        content_parts = []
        
        if chunk_num == 0 and self.current_walk_root:
            tree = self.tree_generator.prepare_tree_header(self.current_walk_root)
            content_parts.append(tree)
        
        content_parts.append(f"CHUNK {chunk_num}")
        
        if metadata and self.extract_metadata:
            content_parts.append("METADATA:")
            
            if metadata["functions"]:
                funcs = ", ".join(sorted(metadata["functions"]))
                content_parts.append(f"FUNCTIONS: {funcs}")
                
            if metadata["classes"]:
                classes = ", ".join(sorted(metadata["classes"]))
                content_parts.append(f"CLASSES: {classes}")
                
            if metadata["imports"]:
                imports = ", ".join(metadata["imports"])
                content_parts.append(f"IMPORTS: {imports}")
                
            if metadata["docstrings"]:
                doc = list(metadata["docstrings"])[0].replace('\n', ' ')[:100]
                content_parts.append(f"DOCSTRING: {doc}")
        
        score = self._calculate_chunk_relevance(text)
        content_parts.append(f"RELEVANCE_SCORE: {score:.2f}")
        
        header = "\n".join(content_parts) + "\n\n"
        full_content = header + text
        
        if self.context_window:
            max_bytes = self.context_window
            content_bytes = full_content.encode('utf-8')
            
            if len(content_bytes) > max_bytes:
                header_bytes = header.encode('utf-8')
                remaining_space = max_bytes - len(header_bytes)
                
                truncated = content_bytes[:len(header_bytes) + remaining_space]
                truncated_str = truncated.decode('utf-8', errors='ignore')
                
                last_newline = truncated_str.rfind('\n')
                if last_newline > len(header):
                    full_content = truncated_str[:last_newline]
        
        os.makedirs(self.output_dir, exist_ok=True)
        chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_num}.txt")
        
        try:
            with open(chunk_path, 'w', encoding='utf-8') as f:
                f.write(full_content)
        except Exception:
            print(f"Failed to write chunk {chunk_num}")

    def _write_minimal_chunk(self, content_bytes, chunk_num) -> None:
        try:
            tree_header = ""
            if chunk_num == 0 and hasattr(self, 'current_walk_root') and self.current_walk_root:
                tree_header = self.tree_generator.prepare_tree_header(self.current_walk_root)
            
            if isinstance(content_bytes, bytes):
                content_str = content_bytes.decode('utf-8', errors='replace')
            else:
                content_str = str(content_bytes)
            
            final_content = tree_header + content_str
            final_bytes = final_content.encode('utf-8')
            
            if self.context_window and len(final_bytes) > self.context_window:
                content_bytes = content_bytes[:self.context_window]

            chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_num}.txt")
            with open(chunk_path, 'wb') as f:
                f.write(final_bytes)
        except Exception:
            print(f"Error writing minimal chunk-{chunk_num}")