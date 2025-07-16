import sys
import argparse
import os
import webbrowser
import time
import threading
from pykomodo.server import app
import socket

KOMODO_VERSION = "0.2.5"

def run_server():
    try: 
        def is_port_available(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('localhost', port))
                    return True
                except OSError:
                    return False
        
        port = 5555
        while not is_port_available(port) and port < 5555:
            port += 1
        
        print(f" Starting Komodo server on http://localhost:{port}")
        print("")
        print("Press Ctrl+C to stop the server")
        
        def open_browser():
            time.sleep(1.0)
            webbrowser.open(f'http://localhost:{port}')
        
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        app.run(host='0.0.0.0', port=port, debug=False)
        
    except ImportError:
        print(f"Error: Could not import Flask server")
        print("Please install flask: pip install flask")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n Komodo server stopped")
        sys.exit(0)
    except Exception:
        print(f" Failed to start server")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Process and chunk codebase",
        epilog="Examples:\n  komodo . --max-chunk-size 2000\n  komodo run",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--version", action="version", version=f"komodo {KOMODO_VERSION}")
    
    parser.add_argument("command", nargs="?", 
                        help="run: Launch web interface")

    parser.add_argument("dirs", nargs="*", default=["."],
                        help="Directories to process")
    
    chunk_group = parser.add_mutually_exclusive_group(required=False)
    chunk_group.add_argument("--equal-chunks", type=int, 
                            help="Split into N equal chunks")
    chunk_group.add_argument("--max-chunk-size", type=int, 
                            help="Maximum tokens/lines per chunk")
    chunk_group.add_argument("--max-tokens", type=int,
                            help="Maximum tokens per chunk")
    
    parser.add_argument("--output-dir", default="chunks",
                        help="Output directory for chunks")
    
    parser.add_argument("--ignore", action="append", default=[],
                        help="Each usage adds one ignore pattern. Example: --ignore '**/node_modules/**' --ignore 'venv'")
    parser.add_argument("--unignore", action="append", default=[],
                        help="Each usage adds one unignore pattern. Example: --unignore '*.md'")
    
    parser.add_argument("--dry-run", action="store_true",
                        help="Show which files would be processed")

    parser.add_argument("--priority", action="append", default=[],
                        help="Example: --priority '*.py,10' --priority 'file2.txt,20'")
    
    parser.add_argument("--num-threads", type=int, default=4,
                        help="Number of processing threads")

    parser.add_argument("--enhanced", action="store_true",
                        help="Enable LLM optimizations")
    
    parser.add_argument("--semantic-chunks", action="store_true",
                        help="Use AST-based chunking for .py files")

    parser.add_argument("--context-window", type=int, default=4096,
                        help="Target LLM context window size")
    parser.add_argument("--min-relevance", type=float, default=0.3,
                        help="Min relevance score 0.0-1.0 (default: 0.3)")
    parser.add_argument("--no-metadata", action="store_true",
                        help="Disable metadata extraction")
    parser.add_argument("--keep-redundant", action="store_true",
                        help="Keep redundant content")
    parser.add_argument("--no-summaries", action="store_true",
                        help="Disable summary generation")

    parser.add_argument("--file-type", type=str, 
                        help="Only chunk files of this type (e.g., 'pdf', 'py')")
                        
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")

    args = parser.parse_args()

    if args.command == "run":
        run_server()
        return

    if not any([args.equal_chunks, args.max_chunk_size, args.max_tokens]):
        parser.error("One of --equal-chunks, --max-chunk-size, or --max-tokens is required (unless using 'run')")

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    priority_rules = []
    for rule in args.priority:
        if not rule:
            continue
        try:
            pattern, score = rule.split(",", 1)
            priority_rules.append((pattern.strip(), int(score.strip())))
        except ValueError:
            print(f"[Error] Priority rule must be 'pattern,score': {rule}", 
                  file=sys.stderr)
            sys.exit(1)

    chunker = None
    try:
        if args.max_tokens:
            try:
                from pykomodo.token_chunker import TokenBasedChunker as ChunkerClass
                if args.verbose:
                    print("Using TokenBasedChunker for token-based chunking")
            except ImportError:
                print("[Error] TokenBasedChunker not available. Please install tiktoken or update pykomodo.", 
                      file=sys.stderr)
                sys.exit(1)
                
            chunker_args = {
                "equal_chunks": args.equal_chunks,
                "max_tokens_per_chunk": args.max_tokens,
                "output_dir": args.output_dir,
                "user_ignore": args.ignore,
                "user_unignore": args.unignore,
                "priority_rules": priority_rules,
                "num_threads": args.num_threads,
                "dry_run": args.dry_run,
                "semantic_chunking": args.semantic_chunks,
                "file_type": args.file_type,
                "verbose": args.verbose
            }
        else:
            if args.enhanced:
                from pykomodo.enhanced_chunker import EnhancedParallelChunker as ChunkerClass
            else:
                from pykomodo.multi_dirs_chunker import ParallelChunker as ChunkerClass
                
            chunker_args = {
                "equal_chunks": args.equal_chunks,
                "max_chunk_size": args.max_chunk_size,
                "output_dir": args.output_dir,
                "user_ignore": args.ignore,
                "user_unignore": args.unignore,
                "priority_rules": priority_rules,
                "num_threads": args.num_threads,
                "dry_run": args.dry_run,
                "semantic_chunking": args.semantic_chunks,
                "file_type": args.file_type
            }
            
            if args.enhanced:
                chunker_args.update({
                    "extract_metadata": not args.no_metadata,
                    "add_summaries": not args.no_summaries,
                    "remove_redundancy": not args.keep_redundant,
                    "context_window": args.context_window,
                    "min_relevance_score": args.min_relevance
                })
    
        chunker = ChunkerClass(**chunker_args)
        
        print("Directory tree structure will be automatically included")
        
        chunker.process_directories(args.dirs)
        
    except Exception:
        print(f"[Error] Processing failed")
        sys.exit(1)
    finally:
        if chunker and hasattr(chunker, 'close'):
            chunker.close()

if __name__ == "__main__":
    main()