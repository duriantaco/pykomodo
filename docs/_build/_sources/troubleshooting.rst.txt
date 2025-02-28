Troubleshooting
================

Common Issues
--------------

- **PDFs Not Chunking:**  
  Ensure PyMuPDF is installed and PDFs aren’t encrypted. Use `--dry-run` to debug.

- **Semantic Chunking Fails:**  
  Syntax errors cause fallback to single chunks. Fix code or disable `--semantic-chunks`.

- **Chunks Too Large:**  
  `--context-window` is a target; use `--max-chunk-size` for strict limits.

- **Chunking ignore not happening:**  
  Check ignore patterns and use `--dry-run` to verify. If in doubt, use the ** wildcard before and after the folder name.

FAQ
----

- **Q: How do I process only specific file types?**  
  **A:** Use `--file-type`, e.g., `--file-type py`.

- **Q: Can I customize ignore patterns?**  
  **A:** Yes, with `--ignore` and `--unignore`.

- **Q: Why isn’t my Python file split semantically?**  
  **A:** Check for syntax errors and ensure `--semantic-chunks` is on.