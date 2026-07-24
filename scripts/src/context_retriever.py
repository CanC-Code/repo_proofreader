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

# ---------------------------------------------------------------------------
# FILE EXTENSION ALLOWLIST
# Only extensions the LLM can meaningfully analyze as source code or config.
# Binary assets, images, svgs, and compiled objects are always excluded.
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {
    '.cpp', '.hpp', '.c', '.h',
    '.java', '.kt', '.kts',
    '.xml', '.json', '.gradle',
    '.py', '.sh', '.md', '.txt',
    '.yaml', '.yml', '.toml', '.properties',
}

# ---------------------------------------------------------------------------
# DIRECTORY SKIP LIST
# These directories are pruned entirely — os.walk will never descend into them.
# Add paths that are pure toolchain noise with no runtime relevance.
# ---------------------------------------------------------------------------
SKIP_DIRS_EXACT = {
    # Build system internals
    '.git', '.gradle', '.idea', 'build', '__pycache__',
    'node_modules', '.cxx', 'intermediates', 'generated',
    # The proofreader engine itself (avoid self-analysis)
    '.proofreader-engine',
    # N64 decompilation host toolchain — these are IDO compiler internals
    # recompiled for the build host, not game or Android runtime code.
    'ido',
    # External tool submodules — differ, processor, splat, asset tools etc.
    # These are upstream projects not authored here.
    'asm-differ', 'asm-processor', 'bk_asset_tool', 'bk_rom_compressor',
    'ido-static-recomp', 'n64splat', 'sound_func_val_unwrap',
    # Assembly stubs — raw MIPS asm, not relevant to Android boot analysis
    'asm',
    # Progress SVG / icon artifacts
    'progress',
    # Android resource image folders (mipmap icons) — not source code
    'mipmap-hdpi', 'mipmap-mdpi', 'mipmap-xhdpi',
    'mipmap-xxhdpi', 'mipmap-xxxhdpi',
}

# ---------------------------------------------------------------------------
# SCORING TIERS
# Files are never dropped — all score >= 1 and appear in exactly one batch.
# Scoring only controls ORDERING: highest score → earliest batch → analyzed
# first by the LLM in the most focused pass.
#
# Tier layout (additive):
#   10000+  Critical Android runtime files (GLRenderer, NativeBridge, etc.)
#    5000   Android/app source tree (Java, Kotlin, CMake, JNI C++)
#    3000   N64 boot/OS/init chain (src/done/, src/core1/os/, src/core1/io/)
#    2000   N64 core engine (src/core1/ root, src/core2/ root logic files)
#    1000   Build scripts (scripts/*.py), Android Gradle/manifest configs
#     500   N64 shared headers (include/)
#     200   Git diff priority (recently modified files)
#      50   Keyword hit (per keyword, up to N hits)
#       1   Baseline — every remaining N64 gameplay C file (src/BGS/, etc.)
# ---------------------------------------------------------------------------

# Android runtime filenames — always analyzed first regardless of path
CRITICAL_ANDROID_FILENAMES = {
    'glrenderer.java', 'glrenderer.kt',
    'nativebridge.cpp', 'nativebridge.hpp', 'nativebridge.java',
    'resource_mgr.cpp',
    'otrservice.java', 'otrservice.kt',
    'mainactivity.java', 'mainactivity.kt',
    'application.java', 'application.kt',
    'bka_safe_base.h',
    'n64_types.h',
    'cmakeLists.txt',
}

# N64 boot-sequence filenames — the verified completed OS/init code
# These are the ground truth for what the Android layer must replicate.
BOOT_SEQUENCE_FILENAMES = {
    'bk_boot_1050.c',   # BK's entry point
    'initialize.c',     # osInitialize / hardware init
    'initthread.c',     # boot thread creation
    'thread.c',         # osCreateThread / osStartThread
    'createthread.c',
    'startthread.c',
    'createmesgqueue.c',
    'sendmesg.c',
    'recvmesg.c',
    'setglobalintmask.c',
    'resetglobalintmask.c',
    'cartrominit.c',    # cart ROM init (PI manager boot)
    'pimgr.c',         # PI manager — DMA controller for ROM reads
    'pirawdma.c',
    'pirawread.c',
    'devmgr.c',        # device manager init
    'inflate.c',       # Rare decompression (overlays decompress on boot)
    'overlays.c',      # overlay loading system
    'll.c',            # low-level helpers
    'si.c',            # serial interface
    'sirawread.c',
    'sirawwrite.c',
    'epirawdma.c',
}

# N64 OS layer filenames (src/core1/os/ — thread/message/timer primitives)
CORE1_OS_FILENAMES = {
    'yieldthread.c', 'stopthread.c', 'destroythread.c',
    'getthreadpri.c', 'settreadpri.c',
    'settimer.c', 'stoptimer.c', 'timerintr.c',
    'seteventmesg.c', 'jammesg.c',
    'pidma.c', 'virtualtophysical.c',
    'gettime.c', 'kdebugserver.c',
    'resetglobalintmask.c', 'setglobalintmask.c',
}

# Keywords that earn a per-hit score boost
SEARCH_KEYWORDS = [
    # Android threading
    'Thread', 'Coroutine', 'runOnUiThread', 'Handler', 'Looper',
    'AsyncTask', 'suspend', 'launch', 'viewModelScope', 'lifecycleScope',
    'synchronized', 'volatile', 'AtomicReference',
    # JNI / NDK
    'JNIEXPORT', 'JNIEnv', 'JavaVM', 'GetEnv', 'AttachCurrentThread',
    'native', 'System.loadLibrary',
    # Android lifecycle
    'onCreate', 'onSurfaceCreated', 'onDrawFrame', 'onSurfaceChanged',
    'GLSurfaceView', 'EGLContext',
    # N64 OS primitives (recompiled equivalents used in Android bridge)
    'osInitialize', 'osCreateThread', 'osStartThread',
    'osSendMesg', 'osRecvMesg', 'osSetIntMask',
    'osCartRomInit', 'osPiStartDma',
    # BKA-specific
    'BKA_', 'bka_', 'RDRAM', 'NativeBridge', 'resource_mgr',
    'OtrService', 'GLRenderer',
]

# Per-batch character budget — safely fits in 24k token context with
# system prompt overhead + diff + output buffer
MAX_BATCH_CHARS = 50000
# Hard cap per individual file — prevents one giant file eating a whole batch
MAX_FILE_CHARS = 12000


# ---------------------------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------------------------

def get_parser(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    target_lang = None
    if ext in ('.cpp', '.hpp', '.c', '.h'):
        target_lang = CPP_LANGUAGE
    elif ext == '.java':
        target_lang = JAVA_LANGUAGE
    elif ext == '.kt' and KOTLIN_SUPPORT:
        target_lang = KOTLIN_LANGUAGE

    if not target_lang:
        return None

    try:
        return Parser(target_lang)
    except TypeError:
        p = Parser()
        if hasattr(p, 'set_language'):
            p.set_language(target_lang)
        else:
            p.language = target_lang
        return p


def _score_file(rel_path, file_name, content, priority_files):
    """
    Assign a priority score to a file. Baseline is 1 — no file is ever dropped.
    Higher score = analyzed in an earlier, more focused batch.
    """
    score = 1
    file_lower = file_name.lower()
    rel_lower = rel_path.replace('\\', '/').lower()

    # --- Tier: Git diff modified files ---
    if rel_path.replace('\\', '/') in priority_files:
        score += 200

    # --- Tier: Critical Android runtime files ---
    if file_lower in CRITICAL_ANDROID_FILENAMES:
        score += 10000

    # --- Tier: Android app source tree ---
    # Matches: Android/app/src/main/cpp/, Android/app/src/main/java/
    if rel_lower.startswith('android/'):
        score += 5000

    # --- Tier: N64 verified boot sequence (src/done/) ---
    if rel_lower.startswith('src/done/'):
        score += 3000
        if file_lower in BOOT_SEQUENCE_FILENAMES:
            score += 1000  # Extra boost for known-critical boot files

    # --- Tier: N64 OS layer (src/core1/os/) ---
    if 'core1/os/' in rel_lower:
        score += 3000
        if file_lower in CORE1_OS_FILENAMES:
            score += 500

    # --- Tier: N64 IO layer (src/core1/io/) ---
    if 'core1/io/' in rel_lower:
        score += 2500

    # --- Tier: N64 core1 root (init, inflate, ll, audio) ---
    if rel_lower.startswith('src/core1/') and 'core1/os/' not in rel_lower and 'core1/io/' not in rel_lower:
        score += 2000

    # --- Tier: Build and conversion scripts ---
    if rel_lower.startswith('scripts/'):
        score += 1000

    # --- Tier: Shared N64 headers ---
    if rel_lower.startswith('include/'):
        score += 500

    # --- Tier: Android Gradle / manifest configs (not in Android/ subtree already) ---
    if file_lower in {'build.gradle', 'settings.gradle', 'androidmanifest.xml',
                      'gradle.properties', 'proguard-rules.pro'}:
        score += 800

    # --- Keyword hits in content ---
    for kw in SEARCH_KEYWORDS:
        if kw in content:
            score += 50

    # Everything else (src/core2/, src/BGS/, src/CC/, etc.) stays at score=1
    # and lands in later batches — still analyzed, just lowest priority.
    return score


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def fetch_all_files_batched(repo_path, diff_data):
    """
    Recursively walk the entire repository. Score every eligible source file.
    Return a list of context_map dicts (batches), each <= MAX_BATCH_CHARS,
    sorted so the highest-priority files are in the earliest batches.

    GUARANTEE: every eligible file appears in exactly one batch. Nothing dropped.
    """
    priority_files = set()
    if diff_data and 'modified_files' in diff_data:
        for f in diff_data['modified_files']:
            priority_files.add(f.replace('\\', '/'))

    all_scored_files = []
    skipped_count = 0

    print(f"[INFO] Walking repository: {repo_path}")

    for root, dirs, files in os.walk(repo_path, topdown=True):
        # Prune skip-listed directories IN PLACE so os.walk never descends.
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIRS_EXACT and not d.startswith('.')
        ]

        rel_root = os.path.relpath(root, repo_path).replace('\\', '/')

        for file_name in files:
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                skipped_count += 1
                continue

            full_path = os.path.join(root, file_name)
            rel_path = os.path.join(rel_root, file_name).replace('\\', '/')
            # Strip leading './' if present
            if rel_path.startswith('./'):
                rel_path = rel_path[2:]

            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                skipped_count += 1
                continue

            score = _score_file(rel_path, file_name, content, priority_files)
            all_scored_files.append((score, rel_path, content))

    print(f"[INFO] Total eligible files found: {len(all_scored_files)} "
          f"(skipped {skipped_count} non-text/binary files)")

    if not all_scored_files:
        return []

    # Sort descending: highest-scored files first → earliest batches → first LLM passes
    all_scored_files.sort(key=lambda x: x[0], reverse=True)

    # Partition into batches
    batches = []
    current_batch = {}
    current_chars = 0

    for score, rel_path, content in all_scored_files:
        if len(content) > MAX_FILE_CHARS:
            display_content = (
                content[:MAX_FILE_CHARS]
                + f"\n...[FILE TRUNCATED AT {MAX_FILE_CHARS} CHARS — "
                  f"{len(content) - MAX_FILE_CHARS} chars omitted]..."
            )
        else:
            display_content = content

        file_chars = len(display_content)

        if current_chars + file_chars > MAX_BATCH_CHARS and current_batch:
            batches.append(current_batch)
            current_batch = {}
            current_chars = 0

        current_batch[rel_path] = display_content
        current_chars += file_chars
        print(
            f"[DEBUG] Batch {len(batches) + 1:>3} | "
            f"Score:{score:>6} | {rel_path} ({file_chars} chars)"
        )

    if current_batch:
        batches.append(current_batch)

    total_files = sum(len(b) for b in batches)
    print(f"\n[INFO] Batching complete: {total_files} files → {len(batches)} pass(es).")
    for i, batch in enumerate(batches, start=1):
        batch_chars = sum(len(v) for v in batch.values())
        print(f"  Pass {i:>3}: {len(batch):>4} files, {batch_chars:>6} chars")

    return batches


def fetch_relevant_files(repo_path, diff_data, issue_description=""):
    """
    Compatibility shim — returns only the first (highest-priority) batch.
    For full recursive analysis use fetch_all_files_batched() directly.
    """
    batches = fetch_all_files_batched(repo_path, diff_data)
    return batches[0] if batches else {}
