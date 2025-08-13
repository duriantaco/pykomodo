import fitz
import re

class PDFProcessor:
    def __init__(self, max_chunk_size):
        self.max_chunk_size = max_chunk_size
    
    def extract_text_from_pdf(self, path):
        try:
            text = ""
            with fitz.open(path) as doc:
                for page in doc:
                    text += page.get_text("text")
            return text
        except Exception:
            print(f"Error extracting text from PDF: {path}")
            return ""
    
    def extract_pdf_paragraphs(self, path):
        try:
            paragraphs = []
            with fitz.open(path) as doc:
                for page in doc:
                    text = page.get_text("text")
                    page_paras = text.split("\n\n")
                    for para in page_paras:
                        stripped = para.strip()
                        if stripped:
                            paragraphs.append(stripped)
            if len(paragraphs) <= 1:
                paragraphs = [ln.strip() for ln in text.splitlines() if ln.strip()]
            return paragraphs
        except Exception:
            print(f"Error extracting paragraphs from PDF: {path}")
            return []
    
    def process_pdf_for_chunking(self, path, start_idx, chunk_writer):
        try:
            all_pages_content = []
            with fitz.open(path) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    page_text = self._extract_page_text(page, page_num)
                    all_pages_content.append(page_text)
            full_document = "\n\n".join(all_pages_content)
            return self._chunk_pdf_content(path, full_document, start_idx, chunk_writer)

            
        except Exception as e:
            print(f"Error processing PDF {path}: {e}")
            error_content = (
                "="*80 + "\n"
                + f"CHUNK {start_idx + 1}\n"
                + "="*80 + "\n\n"
                + "="*40 + "\n"
                + f"File: {path}\n"
                + "="*40 + "\n"
                + f"[Error processing PDF: {str(e)}]\n"
            )
            chunk_writer.write_chunk(error_content.encode("utf-8"), start_idx)
            return start_idx + 1
    
    def _extract_page_text(self, page, page_num):
        text_as_text = page.get_text("text")  
        text_as_html = page.get_text("html")  
        text_as_dict = page.get_text("dict") 

        if "<p>" in text_as_html:
            paragraphs = re.findall(r'<p>(.*?)</p>', text_as_html, re.DOTALL)
            processed_text = []
            
            for p in paragraphs:
                clean_p = re.sub(r'<.*?>', ' ', p)
                clean_p = re.sub(r'&[a-zA-Z]+;', ' ', clean_p)
                clean_p = re.sub(r'\s+', ' ', clean_p).strip()
                if clean_p:
                    processed_text.append(clean_p)
            
            page_text = "\n\n".join(processed_text)
        
        elif len(text_as_dict.get("blocks", [])) > 0:
            blocks = sorted(text_as_dict["blocks"], key=lambda b: b["bbox"][1])
            processed_text = []
            
            for block in blocks:
                if "lines" not in block:
                    continue
                
                block_lines = []
                for line in block["lines"]:
                    if "spans" not in line:
                        continue
                    
                    line_text = " ".join(span["text"] for span in line["spans"] if "text" in span)
                    if line_text.strip():
                        block_lines.append(line_text)
                
                if block_lines:
                    processed_text.append(" ".join(block_lines))
            
            page_text = "\n\n".join(processed_text)
        
        else:
            lines = text_as_text.split('\n')
            paragraphs = []
            current_paragraph = []
            
            for line in lines:
                line = line.strip()
                words = line.split()
                if len(words) <= 2 and not line.endswith('.') and not line.endswith(':'):
                    current_paragraph.append(line)
                else:
                    if current_paragraph:
                        paragraphs.append(" ".join(current_paragraph))
                        current_paragraph = []
                    if line:
                        paragraphs.append(line)
            
            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
            
            page_text = "\n\n".join(paragraphs)
        
        page_content = f"--- Page {page_num + 1} ---\n\n{page_text}"
        return page_content
    
    def _chunk_pdf_content(self, path, content, start_idx, chunk_writer):
        paragraphs = content.split("\n\n")
        current_chunk = []
        current_size = 0
        idx = start_idx
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
                
            para_size = len(paragraph.split())
            
            if current_size + para_size > self.max_chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                final_text = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{chunk_text}"
                chunk_writer.write_chunk(final_text.encode("utf-8"), idx)
                idx += 1
                current_chunk = []
                current_size = 0
            
            current_chunk.append(paragraph)
            current_size += para_size
        
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            final_text = f"{'='*80}\nFILE: {path}\n{'='*80}\n\n{chunk_text}"
            chunk_writer.write_chunk(final_text.encode("utf-8"), idx)
            idx += 1
        
        return idx