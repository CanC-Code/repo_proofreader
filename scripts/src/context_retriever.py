import os
from tree_sitter import Language, Parser
import tree_sitter_cpp
import tree_sitter_java

def get_parser_for_file(file_path):
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
    parser = get_parser_for_file(file_path)
    if not parser:
        return None

    with open(file_path, 'r') as f:
        code = f.read()
    
    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node
    
    extracted_snippets = []
    target_node_types = [
        'function_definition', 
        'method_declaration', 
        'class_declaration'
    ]

    # Perform a top-level scan for key structural blocks
    for child in root_node.children:
        if child.type in target_node_types:
            extracted_snippets.append(code[child.start_byte:child.end_byte])

    if extracted_snippets:
        return "\n...\n".join(extracted_snippets)
    
    return code 

def fetch_relevant_files(repo_path, diff_data):
    context_map = {}
    for file_path in diff_data['modified_files']:
        full_path = os.path.join(repo_path, file_path)
        if os.path.exists(full_path):
            symbol_data = extract_symbols(full_path)
            context_map[file_path] = symbol_data
            
    return context_map
