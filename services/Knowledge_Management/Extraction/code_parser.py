import ast
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import re
import tree_sitter
import javalang

# code_parser.py (extracts entities and relationships from code files)
@dataclass
class CodeEntity:
    name: str
    type: str
    line_number: int
    end_line: Optional[int] = None
    file_path: Optional[str] = None
    content: Optional[str] = None
    parent: Optional[str] = None
    parameters: Optional[List[str]] = None
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    decorators: Optional[List[str]] = None
    visibility: Optional[str] = None  # 'public', 'private', 'protected'
    is_static: bool = False
    is_abstract: bool = False
    is_final: bool = False


@dataclass
class CodeRelationship:
    from_entity: str
    to_entity: str
    relationship_type: str  # 'inherits', 'implements', 'calls', 'imports', 'belongs_to'
    line_number: int
    metadata: Optional[Dict[str, Any]] = None


class CodeParser:
    def __init__(self):
        self.entities = []
        self.relationships = []
        
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse a code file and extract entities and relationships"""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.py':
            return self._parse_python(file_path)
        elif file_extension == '.java':
            return self._parse_java(file_path)
        elif file_extension in ['.js', '.ts', '.jsx', '.tsx']:
            return self._parse_javascript(file_path)
        elif file_extension in ['.cpp', '.c', '.h', '.hpp']:
            return self._parse_cpp(file_path)
        elif file_extension in ['.cs']:
            return self._parse_csharp(file_path)
        elif file_extension in ['.php']:
            return self._parse_php(file_path)
        else:
            return self._parse_generic(file_path)
    
    def _parse_python(self, file_path: str) -> Dict[str, Any]:
        """Parse Python files using built-in AST"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            self.entities = []
            self.relationships = []
            
            # Track current class context
            current_class = None
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Extract class
                    class_entity = CodeEntity(
                        name=node.name,
                        type='class',
                        line_number=node.lineno,
                        end_line=node.end_lineno,
                        file_path=file_path,
                        content=ast.unparse(node),
                        decorators=[ast.unparse(d) for d in node.decorator_list] if node.decorator_list else [],
                        docstring=ast.get_docstring(node)
                    )
                    self.entities.append(class_entity)
                    current_class = node.name
                    
                    # Add inheritance relationships
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            self.relationships.append(CodeRelationship(
                                from_entity=node.name,
                                to_entity=base.id,
                                relationship_type='inherits',
                                line_number=node.lineno
                            ))
                
                elif isinstance(node, ast.FunctionDef):
                    # Extract function/method
                    entity_type = 'method' if current_class else 'function'
                    parent = current_class if current_class else None
                    
                    # Extract parameters
                    parameters = [arg.arg for arg in node.args.args]
                    
                    # Extract return type annotation
                    return_type = None
                    if node.returns:
                        return_type = ast.unparse(node.returns)
                    
                    func_entity = CodeEntity(
                        name=node.name,
                        type=entity_type,
                        line_number=node.lineno,
                        end_line=node.end_lineno,
                        file_path=file_path,
                        content=ast.unparse(node),
                        parent=parent,
                        parameters=parameters,
                        return_type=return_type,
                        decorators=[ast.unparse(d) for d in node.decorator_list] if node.decorator_list else [],
                        docstring=ast.get_docstring(node)
                    )
                    self.entities.append(func_entity)
                    
                    # Add relationship to parent class if it's a method
                    if current_class:
                        self.relationships.append(CodeRelationship(
                            from_entity=f"{current_class}.{node.name}",
                            to_entity=current_class,
                            relationship_type='belongs_to',
                            line_number=node.lineno
                        ))
                
                elif isinstance(node, ast.Import):
                    # Extract imports
                    for alias in node.names:
                        import_entity = CodeEntity(
                            name=alias.name,
                            type='import',
                            line_number=node.lineno,
                            file_path=file_path,
                            content=f"import {alias.name}"
                        )
                        self.entities.append(import_entity)
                
                elif isinstance(node, ast.ImportFrom):
                    # Extract from imports
                    module_name = node.module or ''
                    for alias in node.names:
                        import_entity = CodeEntity(
                            name=f"{module_name}.{alias.name}",
                            type='import',
                            line_number=node.lineno,
                            file_path=file_path,
                            content=f"from {module_name} import {alias.name}"
                        )
                        self.entities.append(import_entity)
                
                elif isinstance(node, ast.Assign):
                    # Extract variable assignments
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_entity = CodeEntity(
                                name=target.id,
                                type='variable',
                                line_number=node.lineno,
                                file_path=file_path,
                                content=ast.unparse(node),
                                parent=current_class
                            )
                            self.entities.append(var_entity)
                
                elif isinstance(node, ast.Call):
                    # Extract function calls
                    if isinstance(node.func, ast.Name):
                        call_entity = CodeEntity(
                            name=node.func.id,
                            type='call',
                            line_number=node.lineno,
                            file_path=file_path,
                            content=ast.unparse(node)
                        )
                        self.entities.append(call_entity)
            
            return self._format_results()
            
        except Exception as e:
            return {
                'entities': [],
                'relationships': [],
                'error': f"Error parsing Python file: {str(e)}"
            }
    
    def _parse_java(self, file_path: str) -> Dict[str, Any]:
        """Parse Java files using javalang"""
        if not JAVALANG_AVAILABLE:
            return {
                'entities': [],
                'relationships': [],
                'error': "javalang library not available. Install with: pip install javalang"
            }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = javalang.parse.parse(content)
            self.entities = []
            self.relationships = []
            
            # Extract classes
            for path, node in tree:
                if isinstance(node, javalang.tree.ClassDeclaration):
                    # Extract class
                    class_entity = CodeEntity(
                        name=node.name,
                        type='class',
                        line_number=getattr(node, 'position', None),
                        file_path=file_path,
                        content=str(node),
                        docstring=node.documentation
                    )
                    self.entities.append(class_entity)
                    
                    # Add inheritance relationships
                    if node.extends:
                        self.relationships.append(CodeRelationship(
                            from_entity=node.name,
                            to_entity=node.extends.name,
                            relationship_type='inherits',
                            line_number=getattr(node, 'position', 0)
                        ))
                    
                    # Extract methods
                    if node.body:
                        for member in node.body:
                            if isinstance(member, javalang.tree.MethodDeclaration):
                                method_entity = CodeEntity(
                                    name=member.name,
                                    type='method',
                                    line_number=getattr(member, 'position', 0),
                                    file_path=file_path,
                                    content=str(member),
                                    parent=node.name,
                                    parameters=[param.name for param in member.parameters] if member.parameters else [],
                                    return_type=str(member.return_type) if member.return_type else None,
                                    docstring=member.documentation,
                                    visibility=member.modifiers[0] if member.modifiers else None,
                                    is_static='static' in member.modifiers if member.modifiers else False,
                                    is_abstract='abstract' in member.modifiers if member.modifiers else False,
                                    is_final='final' in member.modifiers if member.modifiers else False
                                )
                                self.entities.append(method_entity)
                                
                                # Add relationship to class
                                self.relationships.append(CodeRelationship(
                                    from_entity=f"{node.name}.{member.name}",
                                    to_entity=node.name,
                                    relationship_type='belongs_to',
                                    line_number=getattr(member, 'position', 0)
                                ))
                            
                            elif isinstance(member, javalang.tree.FieldDeclaration):
                                # Extract fields
                                for declarator in member.declarators:
                                    field_entity = CodeEntity(
                                        name=declarator.name,
                                        type='variable',
                                        line_number=getattr(member, 'position', 0),
                                        file_path=file_path,
                                        content=str(member),
                                        parent=node.name,
                                        visibility=member.modifiers[0] if member.modifiers else None,
                                        is_static='static' in member.modifiers if member.modifiers else False,
                                        is_final='final' in member.modifiers if member.modifiers else False
                                    )
                                    self.entities.append(field_entity)
            
            return self._format_results()
            
        except Exception as e:
            return {
                'entities': [],
                'relationships': [],
                'error': f"Error parsing Java file: {str(e)}"
            }
    
    def _parse_javascript(self, file_path: str) -> Dict[str, Any]:
        """Parse JavaScript/TypeScript files using tree-sitter or regex fallback"""
        if TREE_SITTER_AVAILABLE:
            return self._parse_javascript_treesitter(file_path)
        else:
            return self._parse_javascript_regex(file_path)
    
    def _parse_javascript_treesitter(self, file_path: str) -> Dict[str, Any]:
        """Parse JavaScript using tree-sitter"""
        try:
            # This would require tree-sitter-javascript grammar
            # For now, fall back to regex parsing
            return self._parse_javascript_regex(file_path)
        except Exception as e:
            return {
                'entities': [],
                'relationships': [],
                'error': f"Error parsing JavaScript with tree-sitter: {str(e)}"
            }
    
    def _parse_javascript_regex(self, file_path: str) -> Dict[str, Any]:
        """Parse JavaScript using regex patterns"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.entities = []
            self.relationships = []
            current_class = None
            
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Class detection
                class_match = re.search(r'class\s+(\w+)(?:\s+extends\s+(\w+))?', line)
                if class_match:
                    class_name = class_match.group(1)
                    parent_class = class_match.group(2)
                    
                    class_entity = CodeEntity(
                        name=class_name,
                        type='class',
                        line_number=line_num,
                        file_path=file_path,
                        content=line
                    )
                    self.entities.append(class_entity)
                    current_class = class_name
                    
                    if parent_class:
                        self.relationships.append(CodeRelationship(
                            from_entity=class_name,
                            to_entity=parent_class,
                            relationship_type='inherits',
                            line_number=line_num
                        ))
                
                # Function/Method detection
                func_match = re.search(r'(?:function\s+)?(\w+)\s*\([^)]*\)\s*{?', line)
                if func_match and not line.startswith('//'):
                    func_name = func_match.group(1)
                    entity_type = 'method' if current_class else 'function'
                    
                    func_entity = CodeEntity(
                        name=func_name,
                        type=entity_type,
                        line_number=line_num,
                        file_path=file_path,
                        content=line,
                        parent=current_class
                    )
                    self.entities.append(func_entity)
                    
                    if current_class:
                        self.relationships.append(CodeRelationship(
                            from_entity=f"{current_class}.{func_name}",
                            to_entity=current_class,
                            relationship_type='belongs_to',
                            line_number=line_num
                        ))
                
                # Variable detection
                var_match = re.search(r'(?:const|let|var)\s+(\w+)', line)
                if var_match:
                    var_name = var_match.group(1)
                    var_entity = CodeEntity(
                        name=var_name,
                        type='variable',
                        line_number=line_num,
                        file_path=file_path,
                        content=line,
                        parent=current_class
                    )
                    self.entities.append(var_entity)
                
                # Import detection
                import_match = re.search(r'import\s+(?:{([^}]+)}|(\w+))\s+from', line)
                if import_match:
                    imports = import_match.group(1) or import_match.group(2)
                    if imports:
                        for imp in imports.split(','):
                            imp_name = imp.strip()
                            import_entity = CodeEntity(
                                name=imp_name,
                                type='import',
                                line_number=line_num,
                                file_path=file_path,
                                content=line
                            )
                            self.entities.append(import_entity)
            
            return self._format_results()
            
        except Exception as e:
            return {
                'entities': [],
                'relationships': [],
                'error': f"Error parsing JavaScript file: {str(e)}"
            }
    
    def _parse_cpp(self, file_path: str) -> Dict[str, Any]:
        """Parse C++ files using regex patterns"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.entities = []
            self.relationships = []
            current_class = None
            
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Class detection
                class_match = re.search(r'class\s+(\w+)(?:\s*:\s*(?:public|private|protected)\s+(\w+))?', line)
                if class_match:
                    class_name = class_match.group(1)
                    parent_class = class_match.group(2)
                    
                    class_entity = CodeEntity(
                        name=class_name,
                        type='class',
                        line_number=line_num,
                        file_path=file_path,
                        content=line
                    )
                    self.entities.append(class_entity)
                    current_class = class_name
                    
                    if parent_class:
                        self.relationships.append(CodeRelationship(
                            from_entity=class_name,
                            to_entity=parent_class,
                            relationship_type='inherits',
                            line_number=line_num
                        ))
                
                # Function detection
                func_match = re.search(r'(\w+)\s+(\w+)\s*\([^)]*\)\s*{?', line)
                if func_match and not line.startswith('//'):
                    return_type = func_match.group(1)
                    func_name = func_match.group(2)
                    
                    # Skip if it's a variable declaration
                    if return_type in ['int', 'float', 'double', 'char', 'bool', 'string', 'void']:
                        entity_type = 'method' if current_class else 'function'
                        
                        func_entity = CodeEntity(
                            name=func_name,
                            type=entity_type,
                            line_number=line_num,
                            file_path=file_path,
                            content=line,
                            parent=current_class,
                            return_type=return_type
                        )
                        self.entities.append(func_entity)
                        
                        if current_class:
                            self.relationships.append(CodeRelationship(
                                from_entity=f"{current_class}.{func_name}",
                                to_entity=current_class,
                                relationship_type='belongs_to',
                                line_number=line_num
                            ))
            
            return self._format_results()
            
        except Exception as e:
            return {
                'entities': [],
                'relationships': [],
                'error': f"Error parsing C++ file: {str(e)}"
            }
    
    def _parse_csharp(self, file_path: str) -> Dict[str, Any]:
        """Parse C# files using regex patterns"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.entities = []
            self.relationships = []
            current_class = None
            
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Class detection
                class_match = re.search(r'(?:public\s+)?class\s+(\w+)(?:\s*:\s*(\w+))?', line)
                if class_match:
                    class_name = class_match.group(1)
                    parent_class = class_match.group(2)
                    
                    class_entity = CodeEntity(
                        name=class_name,
                        type='class',
                        line_number=line_num,
                        file_path=file_path,
                        content=line
                    )
                    self.entities.append(class_entity)
                    current_class = class_name
                    
                    if parent_class:
                        self.relationships.append(CodeRelationship(
                            from_entity=class_name,
                            to_entity=parent_class,
                            relationship_type='inherits',
                            line_number=line_num
                        ))
                
                # Method detection
                method_match = re.search(r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:virtual\s+)?(?:override\s+)?(\w+)\s+(\w+)\s*\([^)]*\)', line)
                if method_match and not line.startswith('//'):
                    return_type = method_match.group(1)
                    method_name = method_match.group(2)
                    
                    method_entity = CodeEntity(
                        name=method_name,
                        type='method',
                        line_number=line_num,
                        file_path=file_path,
                        content=line,
                        parent=current_class,
                        return_type=return_type
                    )
                    self.entities.append(method_entity)
                    
                    if current_class:
                        self.relationships.append(CodeRelationship(
                            from_entity=f"{current_class}.{method_name}",
                            to_entity=current_class,
                            relationship_type='belongs_to',
                            line_number=line_num
                        ))
            
            return self._format_results()
            
        except Exception as e:
            return {
                'entities': [],
                'relationships': [],
                'error': f"Error parsing C# file: {str(e)}"
            }
    
    def _parse_php(self, file_path: str) -> Dict[str, Any]:
        """Parse PHP files using regex patterns"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.entities = []
            self.relationships = []
            current_class = None
            
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Class detection
                class_match = re.search(r'class\s+(\w+)(?:\s+extends\s+(\w+))?', line)
                if class_match:
                    class_name = class_match.group(1)
                    parent_class = class_match.group(2)
                    
                    class_entity = CodeEntity(
                        name=class_name,
                        type='class',
                        line_number=line_num,
                        file_path=file_path,
                        content=line
                    )
                    self.entities.append(class_entity)
                    current_class = class_name
                    
                    if parent_class:
                        self.relationships.append(CodeRelationship(
                            from_entity=class_name,
                            to_entity=parent_class,
                            relationship_type='inherits',
                            line_number=line_num
                        ))
                
                # Function/Method detection
                func_match = re.search(r'(?:public|private|protected)?\s*function\s+(\w+)\s*\([^)]*\)', line)
                if func_match and not line.startswith('//'):
                    func_name = func_match.group(1)
                    entity_type = 'method' if current_class else 'function'
                    
                    func_entity = CodeEntity(
                        name=func_name,
                        type=entity_type,
                        line_number=line_num,
                        file_path=file_path,
                        content=line,
                        parent=current_class
                    )
                    self.entities.append(func_entity)
                    
                    if current_class:
                        self.relationships.append(CodeRelationship(
                            from_entity=f"{current_class}.{func_name}",
                            to_entity=current_class,
                            relationship_type='belongs_to',
                            line_number=line_num
                        ))
            
            return self._format_results()
            
        except Exception as e:
            return {
                'entities': [],
                'relationships': [],
                'error': f"Error parsing PHP file: {str(e)}"
            }
    
    def _parse_generic(self, file_path: str) -> Dict[str, Any]:
        """Generic parser for other file types"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.entities = []
            self.relationships = []
            
            # Create a simple file entity
            file_entity = CodeEntity(
                name=Path(file_path).name,
                type='file',
                line_number=1,
                file_path=file_path,
                content=content[:500] + "..." if len(content) > 500 else content
            )
            self.entities.append(file_entity)
            
            return self._format_results()
            
        except Exception as e:
            return {
                'entities': [],
                'relationships': [],
                'error': f"Error parsing file: {str(e)}"
            }
    
    def _format_results(self) -> Dict[str, Any]:
        """Format the parsing results for database insertion"""
        entities_data = [asdict(entity) for entity in self.entities]
        relationships_data = [asdict(rel) for rel in self.relationships]
        
        return {
            'entities': entities_data,
            'relationships': relationships_data,
            'error': None
        }
