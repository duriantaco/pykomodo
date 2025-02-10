from src.multi_dirs_chunker import ParallelChunker
import os

class EnhancedParallelChunker(ParallelChunker):
    def __init__(
        self,
        equal_chunks=None,
        max_chunk_size=None,
        output_dir="chunks",
        user_ignore=None,
        user_unignore=None,
        binary_extensions=None,
        priority_rules=None,
        num_threads=4,
        extract_metadata=True,
        add_summaries=True,
        remove_redundancy=True,
        context_window=4096,  
        min_relevance_score=0.3
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
        """Extract key metadata from file content."""
        metadata = {
            "functions": [],
            "classes": [],
            "imports": [],
            "docstrings": []
        }
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('def '):
                metadata['functions'].append(line[4:line.find('(')])
            elif line.startswith('class '):
                metadata['classes'].append(line[6:line.find('(')])
            elif line.startswith('import ') or line.startswith('from '):
                metadata['imports'].append(line)
                
        docstring = ''
        if '"""' in content:
            start = content.find('"""') + 3
            end = content.find('"""', start)
            if end > start:
                docstring = content[start:end].strip()
                metadata['docstrings'].append(docstring)
                
        return metadata

    def _calculate_chunk_relevance(self, chunk_content):
        """Calculate relevance score for chunk based on:
        - Code/comment ratio
        - Function/class density
        - Documentation quality
        - Import significance
        """
        score = 1.0
        
        code_lines = len([l for l in chunk_content.split('\n') if l.strip() and not l.strip().startswith('#')])
        comment_lines = len([l for l in chunk_content.split('\n') if l.strip().startswith('#')])
        if code_lines > 0:
            ratio = comment_lines / code_lines
            if ratio > 0.7: 
                score *= 0.8
            elif ratio < 0.1:  
                score *= 0.9
                
        if 'def ' in chunk_content or 'class ' in chunk_content:
            score *= 1.2
            
        if '"""' in chunk_content:
            score *= 1.1
            
        return min(1.0, score)

    def _remove_redundancy(self, chunks):
        """Remove redundant content across chunks."""
        seen_content = set()
        unique_chunks = []
        
        for chunk in chunks:
            content_hash = hash(self._normalize_content(chunk))
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_chunks.append(chunk)
                
        return unique_chunks

    def _normalize_content(self, content):
        """Normalize content for redundancy checking."""
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                lines.append(line)
        return '\n'.join(lines)

    def _write_enhanced_chunk(self, content_bytes, chunk_num, metadata=None):
        """Write chunk with additional LLM-friendly formatting."""
        try:
            content = content_bytes.decode('utf-8', errors='replace')
            
            relevance = self._calculate_chunk_relevance(content)
            if relevance < self.min_relevance_score:
                return  
                
            header = f"""CHUNK {chunk_num}
            RELEVANCE_SCORE: {relevance:.2f}
            """
            if metadata:
                header += "METADATA:\n"
                for key, values in metadata.items():
                    if values:
                        header += f"{key.upper()}: {', '.join(values)}\n"
                        
            header += "="*80 + "\n\n"
            
            enhanced_content = header + content
            
            chunk_path = os.path.join(self.output_dir, f"chunk-{chunk_num}.txt")
            with open(chunk_path, 'w', encoding='utf-8') as f:
                f.write(enhanced_content)
                
        except Exception as e:
            print(f"Error writing enhanced chunk {chunk_num}: {e}")

    def _chunk_by_equal_parts(self):
        """Override to add LLM enhancements."""
        total_content = []
        total_size = 0
        
        for (path, content_bytes, priority) in self.loaded_files:
            try:
                content = content_bytes.decode("utf-8", errors="replace")
                metadata = self._extract_file_metadata(content) if self.extract_metadata else None
                size = len(content)
                total_content.append((path, content, size, metadata))
                total_size += size
            except:
                continue
                
        if not total_content:
            return
            
        chunks = []
        n_chunks = self.equal_chunks
        target_chunk_size = max(1, total_size // n_chunks)
        
        current_chunk = []
        current_size = 0
        
        for i in range(n_chunks):
            chunk_content = []
            chunk_metadata = {
                "functions": [],
                "classes": [],
                "imports": [],
                "docstrings": []
            }
            
            while total_content and current_size < target_chunk_size:
                path, content, size, metadata = total_content[0]
                
                chunk_content.extend([
                    f"\n{'='*40}",
                    f"File: {path}",
                    f"{'='*40}\n",
                    content
                ])
                
                if metadata:
                    for key in chunk_metadata:
                        chunk_metadata[key].extend(metadata[key])
                        
                current_size += size
                total_content.pop(0)
            
            if chunk_content:
                chunk_text = "\n".join(chunk_content)
                if self.remove_redundancy:
                    unique_text = self._remove_redundancy([chunk_text])[0]
                    chunks.append((unique_text, chunk_metadata))
                else:
                    chunks.append((chunk_text, chunk_metadata))
            
            current_size = 0
        
        for i, (content, metadata) in enumerate(chunks):
            self._write_enhanced_chunk(
                content.encode('utf-8'),
                i,
                metadata if self.extract_metadata else None
            )