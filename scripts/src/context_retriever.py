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
    KOTLIN_LANGUAGE = None

CPP_LANGUAGE = Language(tree_sitter_cpp.language())
JAVA_LANGUAGE = Language(tree_sitter_java.language())

# Extensions the engine can meaningfully analyze
ALLOWED_EXTENSIONS = {
    '.cpp', '.hpp', '.c', '.h',
    '.java', '.kt', '.kts',
    '.xml', '.json', '.gradle',
    '.py', '.sh', '.md', '.txt',
    '.yaml', '.yml', '.toml', '.properties',
}

# Directories that are never useful to analyze
SKIP_DIR_FRAGMENTS = {
    '.git', '.gradle', '.idea', 'build', '__pycache__',
    'node_modules', '.cxx', 'intermediates', 'generated',
    '.proofreader-engine',
}

# Per-batch character budget (fits safely in 24k token context with system prompt + diff + output)
MAX_BATCH_CHARS = 50000
# Per-file cap to prevent one massive file consuming the whole batch
MAX_FILE_CHARS = 12000

# Keywords that boost a file's priority score
SEARCH_KEYWORDS = [
    "Thread", "Coroutine", "JNIEXPORT", "native", "onCreate",
    "Surface", "Extraction", "ROM", "MainActivity", "NativeBridge",
    "GLRenderer", "runOnUiThread", "Handler", "Looper", "AsyncTask",
    "suspend", "launch", "viewModelScope", "lifecycleScope",
    "synchronized", "volatile", "AtomicReference",
]

# Filenames that are always highest priority regardless of content
CRITICAL_FILENAMES = {
    "mainactivity.java", "mainactivity.kt",
    "glrenderer.java", "glrenderer.kt",
    "nativebridge.cpp", "nativebridge.c",
    "resource_mgr.cpp", "otrservice.java", "otrservice.kt",
    "application.java", "application.kt",
}


def get_parser(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ('.cpp', '.hpp', '.c', '.h'):
        return Parser(CPP_LANGUAGE)
    elif ext == '.java':
        return Parser(JAVA_LANGUAGE)
    elif ext == '.kt' and KOTLIN_SUPPORT:
        return Parser(KOTLIN_LANGUAGE)
    return None


def _should_skip_dir(root):
    """Return True if this directory should be excluded from analysis."""
    parts = set(root.replace('\\', '/').split('/'))
    return bool(parts & SKIP_DIR_FRAGMENTS)


def _score_file(rel_path, file_name, content, priority_files):
    """
    Assign a priority score to a file.
    All files start at score=1 so none are silently dropped.
    Higher score = analyzed earlier / higher priority within a batch.
    """
    score = 1  # Baseline: every file participates
    file_lower = file_name.lower()
    rel_lower = rel_path.lower()

    # Recently modified in the diff = top priority
    if rel_path in priority_files:
        score += 200

    # Critical well-known filenames
    if file_lower in CRITICAL_FILENAMES:
        score += 10000

    # Android source paths
    if 'android/' in rel_lower or '/src/main/' in rel_lower:
        score += 500

    # JNI / native bridge paths
    if 'jni/' in rel_lower or 'cpp/' in rel_lower or 'native' in rel_lower:
        score += 300

    # Keyword hits in content
    for kw in SEARCH_KEYWORDS:
        if kw in content:
            score += 20

    return score


def fetch_all_files_batched(repo_path, diff_data):
    """
    Walk the entire repository recursively. Score every eligible file.
    Return a list of context_map dicts (batches), each fitting within
    MAX_BATCH_CHARS so the LLM token window is never exceeded.

    Every eligible file appears in exactly one batch — nothing is dropped.
    """
    priority_files = set()
    if diff_data and 'modified_files' in diff_data:
        for f in diff_data['modified_files']:
            priority_files.add(f.replace('\\', '/'))

    all_scored_files = []
    skipped_binary = 0

    print(f"[INFO] Walking repository: {repo_path}")
    for root, dirs, files in os.walk(repo_path, topdown=True):
        # Prune unwanted directories in-place (prevents descending into them)
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIR_FRAGMENTS and not d.startswith('.')
        ]

        if _should_skip_dir(os.path.relpath(root, repo_path)):
            continue

        for file_name in files:
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                skipped_binary += 1
                continue

            full_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(full_path, repo_path).replace('\\', '/')

            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                skipped_binary += 1
                continue

            score = _score_file(rel_path, file_name, content, priority_files)
            all_scored_files.append((score, rel_path, content))

    print(f"[INFO] Total eligible files found: {len(all_scored_files)} "
          f"(skipped {skipped_binary} binary/non-text files)")

    if not all_scored_files:
        return []

    # Sort highest priority first so the first batch contains the most critical files
    all_scored_files.sort(key=lambda x: x[0], reverse=True)

    # Partition into batches that each fit within MAX_BATCH_CHARS
    batches = []
    current_batch = {}
    current_chars = 0

    for score, rel_path, content in all_scored_files:
        # Truncate oversized individual files before adding
        if len(content) > MAX_FILE_CHARS:
            display_content = content[:MAX_FILE_CHARS] + "\n...[TRUNCATED DUE TO SIZE LIMIT]..."
        else:
            display_content = content

        file_chars = len(display_content)

        # If adding this file would overflow the current batch, seal it and start a new one
        if current_chars + file_chars > MAX_BATCH_CHARS and current_batch:
            batches.append(current_batch)
            current_batch = {}
            current_chars = 0

        current_batch[rel_path] = display_content
        current_chars += file_chars
        print(f"[DEBUG] Batch {len(batches) + 1} | Score:{score:>6} | {rel_path} ({file_chars} chars)")

    # Seal the final batch
    if current_batch:
        batches.append(current_batch)

    total_files = sum(len(b) for b in batches)
    print(f"[INFO] Batching complete: {total_files} files split across {len(batches)} pass(es).")
    for i, batch in enumerate(batches, start=1):
        batch_chars = sum(len(v) for v in batch.values())
        print(f"  Pass {i}: {len(batch)} files, {batch_chars} chars")

    return batches


# Legacy single-batch interface kept for any callers that still use it directly
def fetch_relevant_files(repo_path, diff_data, issue_description=""):
    """
    Compatibility shim. Returns only the first (highest-priority) batch.
    Use fetch_all_files_batched() for full recursive multi-pass analysis.
    """
    batches = fetch_all_files_batched(repo_path, diff_data)
    return batches[0] if batches else {}
