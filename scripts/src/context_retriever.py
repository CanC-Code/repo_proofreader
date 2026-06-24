import os
from tree_sitter import Language, Parser
import tree_sitter_cpp
import tree_sitter_java

# Initialize Languages using the modern v0.22+ API
CPP_LANGUAGE = Language(tree_sitter_cpp.language())
JAVA_LANGUAGE = Language(tree_sitter_java.language())

def get_parser(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.cpp', '.hpp', '.c', '.h']:
        return Parser(CPP_LANGUAGE)
    elif ext == '.java':
        return Parser(JAVA_LANGUAGE)
    return None

def fetch_relevant_files(repo_path, diff_data):
    context_map = {}
    if not diff_data or 'modified_files' not in diff_data:
        return context_map

    # Strictly allow only logic files. Ignore XML, YAML, and Assets.
    allowed_extensions = {'.cpp', '.hpp', '.c', '.h', '.java'}
    
    total_chars_appended = 0
    # --- FIX: Strict total cap for context files (~6,000 tokens) ---
    MAX_TOTAL_CHARS = 18000 

    for file_path in diff_data['modified_files']:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in allowed_extensions:
            continue

        full_path = os.path.join(repo_path, file_path)
        if not os.path.exists(full_path):
            continue
            
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
            # Truncate exceptionally long individual files
            MAX_FILE_CHARS = 6000
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + "\n...[FILE TRUNCATED DUE TO SIZE]..."
                
            # Stop adding files if we are about to overflow the context window
            if total_chars_appended + len(content) > MAX_TOTAL_CHARS:
                print(f"[DEBUG] Reached context map size limit. Skipping remaining files.")
                break

            parser = get_parser(file_path)
            if parser:
                context_map[file_path] = content
                total_chars_appended += len(content)
            
        except Exception as e:
            print(f"[WARNING] Could not read or map {file_path}: {e}")
            
    return context_map