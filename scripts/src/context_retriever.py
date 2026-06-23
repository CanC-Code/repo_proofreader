import os
from tree_sitter import Language, Parser
import tree_sitter_cpp  # Requires: pip install tree-sitter-cpp
import tree_sitter_java # Requires: pip install tree-sitter-java

def get_parser_for_file(file_path):
    """Initializes a Tree-sitter parser based on file extension."""
    if file_path.endswith(('.cpp', '.h', '.cc')):
        language = Language(tree_sitter_cpp.language())
    elif file_path.endswith(('.java')):
        language = Language(tree_sitter_java.language())
    else:
        return None
    
    parser = Parser()
    parser.set_language(language)
    return parser

def extract_symbols(file_path):
    """Parses code to extract functional blocks (methods/classes)."""
    parser = get_parser_for_file(file_path)
    if not parser:
        return None

    with open(file_path, 'r') as f:
        code = f.read()
    
    tree = parser.parse(bytes(code, "utf8"))
    
    # Example: Simple logic to extract top-level function definitions
    # In a full implementation, you would walk the tree to find 
    # method_declaration or function_definition nodes.
    return code 

def fetch_relevant_files(repo_path, diff_data):
    """
    Analyzes the diff to determine which files require full context 
    loading vs. summarized extraction.
    """
    context_map = {}
    
    for file_path in diff_data['modified_files']:
        full_path = os.path.join(repo_path, file_path)
        
        if os.path.exists(full_path):
            # For C++/Java, we try to extract structural symbols
            symbol_data = extract_symbols(full_path)
            context_map[file_path] = symbol_data
            
    return context_map
