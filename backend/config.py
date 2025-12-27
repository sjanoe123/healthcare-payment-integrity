"""Shared configuration for the Healthcare Payment Integrity backend.

This module centralizes environment variable access and default values
to prevent drift between modules.
"""

import os

# Database configuration
DB_PATH = os.getenv("DB_PATH", "./data/prototype.db")

# ChromaDB configuration
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
