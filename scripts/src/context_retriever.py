import os
import re
from tree_sitter import Language, Parser
import tree_sitter_cpp
import tree_sitter_java

try:
    import tree_sitter_kotlin
    KOTLIN_SUPPORT = True
    KOTLIN_LANGUAGE = Language(tree_sitter_kotlin.language())
except ImportError:
    KOTLIN_SUPPORT = False

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

def fetch_relevant_files(repo_path, diff_data, issue_description=""):
    context_map = {}
    allowed_extensions = {'.cpp', '.hpp', '.c', '.h', '.java', '.kt', '.xml'}
    
    MAX_TOTAL_CHARS = 18000 
    MAX_FILE_CHARS = 6000
    total_chars_appended = 0

    # 1. Prioritize files from the recent git commit
    priority_files = set()
    if diff_data and 'modified_files' in diff_data:
        for f in diff_data['modified_files']:
            priority_files.add(f)

    # 2. Define global search keywords based on Android UI hangs
    search_keywords = ["Thread", "Coroutine", "JNIEXPORT", "native", "onCreate", "Surface", "Extraction", "ROM", "MainActivity", "NativeBridge"]

    # 3. Walk the entire repository and score files
    repo_files_scored = []
    print("[INFO] Scanning entire repository for relevant context...")
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories (like .git) and build outputs
        if any(part.startswith('.') for part in root.split(os.sep)) or 'build' in root:
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in allowed_extensions:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path)
                
                if rel_path in priority_files:
                    continue 
                    
                score = 0
                # High priority for main Android lifecycle and JNI bridge files
                if "MainActivity" in file or "NativeBridge" in file or "JNI" in file:
                    score += 50
                    
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        # Score file based on how many relevant logic keywords it contains
                        for kw in search_keywords:
                            if kw in content:
                                score += 10
                        
                        if score > 0:
                            repo_files_scored.append((score, rel_path, content))
                except Exception:
                    pass

    # Sort the repository files by their relevance score (highest first)
    repo_files_scored.sort(key=lambda x: x[0], reverse=True)

    # 4. Combine priority diff files with the top-scoring global files
    final_files_to_process = []
    for pf in priority_files:
        full_path = os.path.join(repo_path, pf)
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                final_files_to_process.append((pf, f.read()))
        except:
            pass
            
    for score, rel_path, content in repo_files_scored:
        final_files_to_process.append((rel_path, content))

    # 5. Build the context map safely under the 16k token limit
    for rel_path, content in final_files_to_process:
        if total_chars_appended >= MAX_TOTAL_CHARS:
            print(f"[DEBUG] Global context map size limit reached ({MAX_TOTAL_CHARS} chars).")
            break
            
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n...[FILE TRUNCATED DUE TO SIZE]..."
            
        parser = get_parser(rel_path)
        context_map[rel_path] = content
        total_chars_appended += len(content)
        print(f"[DEBUG] Appended {rel_path} to AI memory.")

    return context_map