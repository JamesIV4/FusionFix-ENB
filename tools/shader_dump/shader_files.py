"""File identities and leaf-name validation shared by the stock shader tools."""
import hashlib
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def leaf(value):
    if not value or value in ('.', '..') or Path(value).name != value or ':' in value or '\\' in value:
        raise ValueError(f'Expected a leaf filename: {value}')
    return value
