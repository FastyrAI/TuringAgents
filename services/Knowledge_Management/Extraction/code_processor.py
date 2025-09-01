from typing import List, Dict, Any
from .code_parser import CodeParser

# code_processor.py (inserts the extracted entities and relationships from code_parser.py into the graph)
class CodeProcessor:
    def __init__(self):
        self.parser = CodeParser()
    
    def process_code_file(self, file_path: str, message_id: str) -> List[Dict[str, Any]]:
        """Process a code file and generate database queries for entities and relationships"""
        # Parse the code file
        parse_result = self.parser.parse_file(file_path)
        
        if parse_result.get('error'):
            print(f"Code parsing error: {parse_result['error']}")
            return []
        
        # print(f"Parsed {len(parse_result['entities'])} entities and {len(parse_result['relationships'])} relationships")
        
        queries = []
        
        # Process entities first
        for entity in parse_result['entities']:
            # print(f"Processing entity: {entity['name']} ({entity['type']})")
            entity_queries = self._create_entity_queries(entity, message_id)
            queries.extend(entity_queries)
        
        # Process relationships
        for relationship in parse_result['relationships']:
            # print(f"Processing relationship: {relationship['from_entity']} -> {relationship['to_entity']} ({relationship['relationship_type']})")
            relationship_queries = self._create_relationship_queries(relationship, message_id)
            queries.extend(relationship_queries)
        
        # print(f"Generated {len(queries)} database queries")
        return queries
    
    def _create_entity_queries(self, entity: Dict[str, Any], message_id: str) -> List[Dict[str, Any]]:
        """Create database queries for code entities"""
        queries = []
        
        # Create the main entity node
        entity_id = f"{entity['name'].lower().replace(' ', '_').replace('.', '_')}_{message_id}"
        
        # Helper function to escape strings for Cypher
        def escape_cypher_string(value):
            if value is None:
                return None
            # Escape single quotes and backslashes
            escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
            # Truncate if too long
            if len(escaped) > 1000:
                escaped = escaped[:1000] + "..."
            return escaped
        
        # Create entity node with all properties
        entity_properties = {
            'id': entity_id,
            'name': escape_cypher_string(entity['name']),
            'type': escape_cypher_string(entity['type']),
            'line_number': entity['line_number'],
            'file_path': escape_cypher_string(entity['file_path']),
            'source_message': message_id
        }
        
        # Add optional properties if they exist
        if entity.get('end_line'):
            entity_properties['end_line'] = entity['end_line']
        if entity.get('parent'):
            entity_properties['parent'] = escape_cypher_string(entity['parent'])
        if entity.get('parameters'):
            entity_properties['parameters'] = escape_cypher_string(str(entity['parameters']))
        if entity.get('return_type'):
            entity_properties['return_type'] = escape_cypher_string(entity['return_type'])
        if entity.get('docstring'):
            entity_properties['docstring'] = escape_cypher_string(entity['docstring'])
        if entity.get('decorators'):
            entity_properties['decorators'] = escape_cypher_string(str(entity['decorators']))
        if entity.get('visibility'):
            entity_properties['visibility'] = escape_cypher_string(entity['visibility'])
        if entity.get('is_static'):
            entity_properties['is_static'] = entity['is_static']
        if entity.get('is_abstract'):
            entity_properties['is_abstract'] = entity['is_abstract']
        if entity.get('is_final'):
            entity_properties['is_final'] = entity['is_final']
        if entity.get('content'):
            entity_properties['content'] = escape_cypher_string(entity['content'])
        
        # Create the MERGE query for the entity
        properties_str = ', '.join([f"{k}: '{v}'" for k, v in entity_properties.items() if v is not None])
        entity_query = f"""
        MERGE (e:CodeEntity {{{properties_str}}})
        """
        queries.append({"query": entity_query})
        
        # Create connection from message to entity
        link_query = f"""
        MATCH (m:Message {{id: '{message_id}'}})
        MATCH (e:CodeEntity {{id: '{entity_id}'}})
        WITH m, e
        MERGE (m)-[:EXTRACTED]->(e)
        """
        queries.append({"query": link_query})
        
        return queries
    
    def _create_relationship_queries(self, relationship: Dict[str, Any], message_id: str) -> List[Dict[str, Any]]:
        """Create database queries for code relationships"""
        queries = []
        
        from_entity = relationship['from_entity']
        to_entity = relationship['to_entity']
        rel_type = relationship['relationship_type']
        line_number = relationship['line_number']
        
        # Helper function to escape strings for Cypher
        def escape_cypher_string(value):
            if value is None:
                return None
            return str(value).replace("\\", "\\\\").replace("'", "\\'")
        
        # Clean the relationship type for database use
        clean_rel_type = rel_type.replace(" ", "_").upper()
        
        # Create the relationship between entities
        rel_query = f"""
        MATCH (from:CodeEntity {{name: '{escape_cypher_string(from_entity)}', source_message: '{message_id}'}})
        MATCH (to:CodeEntity {{name: '{escape_cypher_string(to_entity)}', source_message: '{message_id}'}})
        WITH from, to
        CREATE (from)-[r:{clean_rel_type} {{source_message: '{message_id}', line: {line_number}}}]->(to)
        """
        queries.append({"query": rel_query})
        
        return queries
    
    def _create_function_call_relationships(self, entities: List[Dict[str, Any]], message_id: str) -> List[Dict[str, Any]]:
        """Create relationships for function calls within the code"""
        queries = []
        
        # Find all functions and methods
        functions = [e for e in entities if e['type'] in ['function', 'method']]
        
        # Helper function to escape strings for Cypher
        def escape_cypher_string(value):
            if value is None:
                return None
            return str(value).replace("\\", "\\\\").replace("'", "\\'")
        
        for func in functions:
            content = func.get('content', '')
            if content:
                # Look for function calls in the content
                import re
                
                # Simple pattern to find function calls (this can be enhanced)
                call_pattern = r'(\w+)\s*\('
                calls = re.findall(call_pattern, content)
                
                for call in calls:
                    # Skip if it's the function calling itself or common keywords
                    if call != func['name'] and call not in ['if', 'for', 'while', 'print', 'return']:
                        # Create a CALLS relationship
                        call_query = f"""
                        MATCH (caller:CodeEntity {{name: '{escape_cypher_string(func['name'])}', source_message: '{message_id}'}})
                        MATCH (callee:CodeEntity {{name: '{escape_cypher_string(call)}', source_message: '{message_id}'}})
                        WITH caller, callee
                        CREATE (caller)-[r:CALLS {{source_message: '{message_id}'}}]->(callee)
                        """
                        queries.append({"query": call_query})
        
        return queries
    
    def process_code_with_calls(self, file_path: str, message_id: str) -> List[Dict[str, Any]]:
        """Process code file including function call relationships"""
        # Get basic entities and relationships
        queries = self.process_code_file(file_path, message_id)
        
        # Parse again to get entities for call analysis
        parse_result = self.parser.parse_file(file_path)
        
        if not parse_result.get('error'):
            # Add function call relationships
            call_queries = self._create_function_call_relationships(parse_result['entities'], message_id)
            queries.extend(call_queries)
        
        return queries
