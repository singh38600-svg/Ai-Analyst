import re
from typing import List, Dict, Any

def extract_financial_tables(text: str) -> List[Dict[str, Any]]:
    """
    Finds tabular markdown structure or simple pipe-separated tables in financial texts
    to treat them as single entities.
    """
    tables = []
    # Match pipe tables: lines containing | with at least one separator row like |--
    pattern = r"((?:^[^\n]*\|[^\n]*\n)(?:^[ \t]*\|?[ \t]*:?-+:?[ \t]*\|[^\n]*\n)(?:^[^\n]*\|[^\n]*(?:\n|$))+)"
    for match in re.finditer(pattern, text, re.MULTILINE):
        tables.append({
            "content": match.group(1).strip(),
            "start_idx": match.start(),
            "end_idx": match.end(),
            "type": "markdown_table"
        })
    return tables

def recursive_financial_splitter(text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> List[str]:
    """
    Splits text by cleanly isolating financial tables as distinct chunks,
    preventing any table lines from spilling into general paragraph chunks.
    """
    tables = extract_financial_tables(text)
    
    def split_segment(segment: str, max_sz: int, overlap: int) -> List[str]:
        # Filter out empty or whitespace only lines
        lines = [line.strip() for line in segment.split("\n") if line.strip()]
        # Do not include table markup lines if any accidentally remain
        clean_lines = [line for line in lines if not line.startswith("|")]
        segment_cleaned = "\n".join(clean_lines)
        
        words = segment_cleaned.split()
        if len(words) <= max_sz:
            return [segment_cleaned] if segment_cleaned.strip() else []
        
        chunks = []
        step = max_sz - overlap
        if step <= 0:
            step = max_sz // 2
            
        i = 0
        while i < len(words):
            chunk_words = words[i:i + max_sz]
            chunks.append(" ".join(chunk_words))
            i += step
            if i >= len(words):
                break
        return chunks

    if not tables:
        return split_segment(text, chunk_size, chunk_overlap)
    
    chunks = []
    last_idx = 0
    for tbl in tables:
        # Split text before the table
        before_text = text[last_idx:tbl["start_idx"]]
        if before_text.strip():
            chunks.extend(split_segment(before_text, chunk_size, chunk_overlap))
            
        # Append table as its own isolated chunk
        chunks.append(tbl["content"])
        last_idx = tbl["end_idx"]
        
    # Remaining text after the last table
    after_text = text[last_idx:]
    if after_text.strip():
        chunks.extend(split_segment(after_text, chunk_size, chunk_overlap))
        
    return chunks
