"""
core/data_ingestion/unstructured_loader.py - Layer 4: Data Ingestion

Uses unstructured.io to ingest a wide variety of documents (PDF, Word, HTML, etc.)
and convert them into clean, normalized Markdown/text for the agent.
"""

import os
from pathlib import Path
from typing import List, Optional
from core.log_config import get_logger

_log = get_logger(__name__)

class UnstructuredIngestionEngine:
    def __init__(self):
        self._initialized = False
        
    def _ensure_initialized(self):
        if self._initialized:
            return True
            
        try:
            import unstructured
            self._initialized = True
            return True
        except ImportError:
            _log.warning("unstructured package not installed. Run: pip install unstructured[all-docs]")
            return False

    def ingest_file(self, file_path: str | Path) -> Optional[str]:
        """
        Parses a file (PDF, DOCX, TXT, HTML, etc) and returns the extracted text.
        """
        if not self._ensure_initialized():
            return None
            
        path = Path(file_path)
        if not path.exists():
            _log.error(f"File not found: {path}")
            return None
            
        try:
            from unstructured.partition.auto import partition
            
            _log.info(f"Ingesting file: {path.name}")
            elements = partition(filename=str(path))
            
            # Combine text from all elements
            full_text = "\n\n".join([str(el) for el in elements if str(el).strip()])
            _log.info(f"Successfully extracted {len(full_text)} characters from {path.name}")
            return full_text
            
        except Exception as e:
            _log.error(f"Failed to ingest {path.name} via Unstructured: {e}", exc_info=True)
            return None
            
    def ingest_directory(self, dir_path: str | Path) -> List[dict]:
        """
        Ingests all supported files in a directory.
        Returns a list of dicts: [{"filename": "...", "content": "..."}]
        """
        path = Path(dir_path)
        results = []
        
        if not path.is_dir():
            _log.error(f"Directory not found: {path}")
            return results
            
        for file in path.rglob("*"):
            if file.is_file():
                # Skip common binaries/hidden files that unstructured might struggle with blindly
                if file.name.startswith(".") or file.suffix.lower() in [".db", ".sqlite3", ".pyc", ".png", ".jpg"]:
                    continue
                    
                content = self.ingest_file(file)
                if content:
                    results.append({"filename": file.name, "path": str(file), "content": content})
                    
        return results

    def ingest_url(self, url: str) -> Optional[str]:
        """
        Scrapes and extracts clean markdown/text from a webpage using Unstructured.
        """
        if not self._ensure_initialized():
            return None
            
        try:
            from unstructured.partition.html import partition_html
            
            _log.info(f"Ingesting URL: {url}")
            elements = partition_html(url=url)
            full_text = "\n\n".join([str(el) for el in elements if str(el).strip()])
            _log.info(f"Successfully extracted {len(full_text)} characters from {url}")
            return full_text
            
        except Exception as e:
            _log.error(f"Failed to ingest URL {url} via Unstructured: {e}", exc_info=True)
            return None

# Singleton instance
default_ingestion_engine = UnstructuredIngestionEngine()
