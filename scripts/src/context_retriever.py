import os
from tree_sitter import Language, Parser
import tree_sitter_cpp
import tree_sitter_java

# Safely import Kotlin parser, as it's a newly added dependency
try:
    import tree_sitter_kotlin
    KOTLIN_SUPPORT = True
    KOTLIN_LANGUAGE = Language(tree_sitter_kotlin.language())
except ImportError:
    KOTLIN_SUPPORT = False
    print("[WARNING] tree-sitter-kotlin not found. Kotlin files will be ingested as raw text.")

# Initialize standard Languages using the modern v0.22+ API
CPP_LANGUAGE = Language(tree_sitter_cpp.language())
JAVA_LANGUAGE = Language(tree_sitter_java.language())

def get_parser(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.cpp', '.hpp', '.c', '.h']:
        return Parser(CPP_LANGUAGE)
    elif ext == '.java':
        return Parser(JAVA_LANGUAGE)
    elif ext == '.kt' and KOTLIN_SUPPORT:
        return Parser(KOTLIN_LANGUAGE)
    return None

def fetch_relevant_files(repo_path, diff_data):
    context_map = {}
    if not diff_data or 'modified_files' not in diff_data:
        return context_map

    # ADDED: .kt (Kotlin) and .xml (Android Manifests/Layouts) to allowed logic files
    allowed_extensions = {'.cpp', '.hpp', '.c', '.h', '.java', '.kt', '.xml'}
    
    total_chars_appended = 0
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
                
            MAX_FILE_CHARS = 6000
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + "\n...[FILE TRUNCATED DUE TO SIZE]..."
                
            if total_chars_appended + len(content) > MAX_TOTAL_CHARS:
                print(f"[DEBUG] Reached context map size limit. Skipping remaining files.")
                break

            parser = get_parser(file_path)
            # If parser exists, we validated the AST. If it doesn't (like XML or fallback Kotlin), 
            # we append the raw text anyway so the LLM gets the necessary context.
            context_map[file_path] = content
            total_chars_appended += len(content)
            
        except Exception as e:
            print(f"[WARNING] Could not read or map {file_path}: {e}")
            
    return context_map