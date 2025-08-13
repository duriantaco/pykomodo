from pydantic import BaseModel, Field
from typing import List, Optional

from pykomodo.enhanced_chunker import EnhancedParallelChunker
from pykomodo.multi_dirs_chunker import ParallelChunker

class KomodoConfig(BaseModel):
    directories: List[str] = Field(
        default_factory=lambda: ["."],
        description="Which directories to process"
    )
    equal_chunks: Optional[int] = Field(
        default=None,
        description="Number of equal chunks to produce"
    )
    max_chunk_size: Optional[int] = Field(
        default=None,
        description="Max tokens/lines per chunk"
    )
    output_dir: str = Field(
        default="chunks",
        description="Where chunked files will be stored."
    )
    semantic_chunking: bool = Field(
        default=False,
        description="If True, chunk .py files at function/class boundaries."
    )
    enhanced: bool = Field(
        default=False,
        description="If True, use EnhancedParallelChunker for LLM-related features"
    )
    context_window: int = 4096
    min_relevance_score: float = 0.3
    remove_redundancy: bool = True
    extract_metadata: bool = True

def run_chunker_with_config(config: KomodoConfig):
    if config.enhanced:
        ChunkerClass = EnhancedParallelChunker
    else:
        ChunkerClass = ParallelChunker

    chunker = ChunkerClass(
        equal_chunks=config.equal_chunks,
        max_chunk_size=config.max_chunk_size,
        output_dir=config.output_dir,
        semantic_chunking=config.semantic_chunking,
        context_window=config.context_window if config.enhanced else None,
        min_relevance_score=config.min_relevance_score if config.enhanced else None,
        remove_redundancy=config.remove_redundancy if config.enhanced else None,
        extract_metadata=config.extract_metadata if config.enhanced else None,
    )

    chunker.process_directories(config.directories)
    chunker.close()

if __name__ == "__main__":
    my_config = KomodoConfig(
        directories=["src/", "docs/"],   # or wherever
        equal_chunks=5,
        output_dir="my_chunks",
        semantic_chunking=True,
        enhanced=True 
    )
    run_chunker_with_config(my_config)
