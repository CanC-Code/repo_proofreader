import os
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

    priority_files = set()
    if diff_data and 'modified_files' in diff_data:
        for f in diff_data['modified_files']:
            priority_files.add(f)

    # Core files that MUST be analyzed for UI hangs and JNI deadlocks
    critical_filenames = {
        "mainactivity.java", "mainactivity.kt", 
        "glrenderer.java", "glrenderer.kt",
        "nativebridge.cpp", "nativebridge.c", 
        "resource_mgr.cpp", "otrservice.java", "otrservice.kt"
    }

    search_keywords = ["Thread", "Coroutine", "JNIEXPORT", "native", "onCreate", "Surface", "Extraction", "ROM", "MainActivity", "NativeBridge", "GLRenderer"]

    repo_files_scored = []
    print("[INFO] Scanning for Android-specific logic (Case-Insensitive)...")
    
    for root, dirs, files in os.walk(repo_path):
        if any(part.startswith('.') for part in root.split(os.sep)) or 'build' in root:
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in allowed_extensions:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path).replace('\\', '/')
                
                if rel_path in priority_files:
                    continue 
                    
                score = 0
                file_lower = file.lower()
                rel_path_lower = rel_path.lower()
                
                # 1. GUARANTEED INCLUSION FOR CRITICAL FILES
                if file_lower in critical_filenames:
                    score += 1000
                
                # 2. Boost anything in an android/ folder (Case-Insensitive)
                if "android/" in rel_path_lower:
                    score += 100
                    
                # 3. Boost based on logic keywords
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        for kw in search_keywords:
                            if kw in content:
                                score += 15
                        
                        if score > 0:
                            repo_files_scored.append((score, rel_path, content))
                except Exception:
                    pass

    # Sort so the score=1000 critical files are always first
    repo_files_scored.sort(key=lambda x: x[0], reverse=True)

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

    for rel_path, content in final_files_to_process:
        if total_chars_appended >= MAX_TOTAL_CHARS:
            break
            
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n...[TRUNCATED]..."
            
        # Avoid duplicate appending
        if rel_path not in context_map:
            context_map[rel_path] = content
            total_chars_appended += len(content)
            print(f"[DEBUG] Priority Appended: {rel_path} (Score: {score if 'score' in locals() else 'N/A'})")

    return context_map