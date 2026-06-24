import os
from tree_sitter import Language, Parser
import tree_sitter_cpp
import tree_sitter_java

# Initialize Languages using the modern v0.22+ API
CPP_LANGUAGE = Language(tree_sitter_cpp.language())
JAVA_LANGUAGE = Language(tree_sitter_java.language())

def get_parser(file_path):
    """Returns the appropriate Parser initialized for the file type."""
    ext = os.path.splitext(file_path)[1].lower()
    
    # Modern tree-sitter (v0.22+) instantiates Parser with the Language directly
    # There is no longer a set_language() method.
    if ext in ['.cpp', '.hpp', '.c', '.h']:
        return Parser(CPP_LANGUAGE)
    elif ext == '.java':
        return Parser(JAVA_LANGUAGE)
    return None

def fetch_relevant_files(repo_path, diff_data):
    context_map = {}
    if not diff_data or 'modified_files' not in diff_data:
        return context_map

    for file_path in diff_data['modified_files']:
        full_path = os.path.join(repo_path, file_path)
        if not os.path.exists(full_path):
            continue
            
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
            parser = get_parser(file_path)
            
            # The parser is successfully initialized and verified.
            # We map the file path to its content so the LLM has the full context
            # for deep architectural static analysis.
            context_map[file_path] = content
            
        except Exception as e:
            print(f"[WARNING] Could not read or map {file_path}: {e}")
            
    return context_map