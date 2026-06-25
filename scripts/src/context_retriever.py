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
            priority_files.add(f.replace('\\', '/'))

    # Core files that MUST be analyzed for UI hangs and JNI deadlocks
    critical_filenames = {
        "mainactivity.java", "mainactivity.kt", 
        "glrenderer.java", "glrenderer.kt",
        "nativebridge.cpp", "nativebridge.c", 
        "resource_mgr.cpp", "otrservice.java", "otrservice.kt"
    }

    search_keywords = ["Thread", "Coroutine", "JNIEXPORT", "native", "onCreate", "Surface", "Extraction", "ROM", "MainActivity", "NativeBridge", "GLRenderer"]

    all_scored_files = []
    print("[INFO] Scoring all repository and diff files together (Context Limit Enforcement)...")
    
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and build outputs
        if any(part.startswith('.') for part in root.split(os.sep)) or 'build' in root:
            continue
            
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in allowed_extensions:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_path).replace('\\', '/')
                
                score = 0
                file_lower = file.lower()
                rel_path_lower = rel_path.lower()
                
                # 1. Diff files get a baseline boost so recent changes aren't ignored
                if rel_path in priority_files:
                    score += 50
                
                # 2. GUARANTEED INCLUSION: Overpower everything else
                if file_lower in critical_filenames:
                    score += 10000 
                
                # 3. Boost anything in an android/ folder
                if "android/" in rel_path_lower:
                    score += 500
                    
                # 4. Boost based on logic keywords
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        for kw in search_keywords:
                            if kw in content:
                                score += 20
                        
                        if score > 0:
                            all_scored_files.append((score, rel_path, content))
                except Exception:
                    pass

    # Sort so the 10,000-point critical files are processed first
    all_scored_files.sort(key=lambda x: x[0], reverse=True)

    for score, rel_path, content in all_scored_files:
        if total_chars_appended >= MAX_TOTAL_CHARS:
            break
            
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n...[TRUNCATED DUE TO SIZE LIMIT]..."
            
        # Avoid duplicate appending
        if rel_path not in context_map:
            context_map[rel_path] = content
            total_chars_appended += len(content)
            print(f"[DEBUG] Appended: {rel_path} (Score: {score})")

    return context_map