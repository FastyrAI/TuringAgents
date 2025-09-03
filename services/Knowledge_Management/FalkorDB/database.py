import falkordb
import uuid
from datetime import datetime
from typing import List, Dict, Any
from config import FALKORDB_HOST, FALKORDB_PORT, FALKORDB_USERNAME, FALKORDB_PASSWORD, FALKORDB_GRAPH_NAME

class DatabaseManager:
    def __init__(self):
        self.client = falkordb.FalkorDB(
            host=FALKORDB_HOST,
            port=FALKORDB_PORT,
            username=FALKORDB_USERNAME,
            password=FALKORDB_PASSWORD
        )
        self.graph = self.client.select_graph(FALKORDB_GRAPH_NAME)
    
#   This function is used to avoid conflicts between MERGE and MATCH queries as MERGE creates or updates nodes/edges, and must be executed before MATCH queries. If Match executes before Merge it might fail as data does not exist yet. 
    def execute_queries(self, queries: List[Dict[str, Any]]) -> None:
        """Execute multiple database queries"""

        merge_queries = []
        other_queries = []
        
        for query_data in queries:
            query = query_data["query"].strip()
            if query.upper().startswith("MERGE"):
                merge_queries.append(query_data)
            else:
                other_queries.append(query_data)
        
        # Execute MERGE queries first
        for query_data in merge_queries:
            try:
                self.graph.query(query_data["query"])
            except Exception as e:
                print(f"Error executing MERGE query: {e}")
        
        # Execute other queries after (including MATCH-CREATE combinations)
        for query_data in other_queries:
            try:
                self.graph.query(query_data["query"])
            except Exception as e:
                print(f"Error executing query: {e}")
    
    def get_messages(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieve messages for a specific user"""
        query = f"""
        MATCH (u:User {{id: '{user_id}'}})-[:SENT]->(m:Message)
        RETURN m
        ORDER BY m.timestamp
        """
        
        result = self.graph.query(query)
        messages = []
        
        for record in result.result_set:
            msg = record[0]
            messages.append({
                "message_id": msg.properties.get('id'),
                "content": msg.properties.get('content'),
                "role": msg.properties.get('role'),
                "user_id": msg.properties.get('user_id'),
                "timestamp": msg.properties.get('timestamp')
            })
        
        return messages
    
    def store_file(self, file_id: str, original_filename: str, stored_filename: str, 
                   file_path: str, file_size: int, content_type: str, user_id: str, 
                   description: str = "") -> Dict[str, Any]:
        """Store file metadata in the database"""
        timestamp = datetime.now().isoformat()
        
        query = f"""
        MERGE (u:User {{id: '{user_id}'}})
        CREATE (f:File {{id: $file_id, original_filename: $original_filename, stored_filename: $stored_filename, file_path: $file_path, file_size: $file_size, content_type: $content_type, user_id: $user_id, description: $description, upload_timestamp: $upload_timestamp}})
        CREATE (u)-[:UPLOADED]->(f)
        """
        params = {
            "file_id": file_id,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "file_path": file_path,
            "file_size": file_size,
            "content_type": content_type,
            "user_id": user_id,
            "description": description,
            "upload_timestamp": timestamp
        }
        self.graph.query(query, params)
        
        return {**params}
    
    def get_user_files(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all files uploaded by a user"""
        query = f"""
        MATCH (u:User {{id: '{user_id}'}})-[:UPLOADED]->(f:File)
        RETURN f
        ORDER BY f.upload_timestamp DESC
        """
        
        result = self.graph.query(query)
        files = []
        
        for record in result.result_set:
            file_node = record[0]
            files.append({
                "file_id": file_node.properties.get('id'),
                "original_filename": file_node.properties.get('original_filename'),
                "stored_filename": file_node.properties.get('stored_filename'),
                "file_path": file_node.properties.get('file_path'),
                "file_size": file_node.properties.get('file_size'),
                "content_type": file_node.properties.get('content_type'),
                "user_id": file_node.properties.get('user_id'),
                "description": file_node.properties.get('description'),
                "upload_timestamp": file_node.properties.get('upload_timestamp')
            })
        
        return files
    
    def get_file(self, file_id: str) -> Dict[str, Any]:
        """Get file information by file_id"""
        query = f"""
        MATCH (f:File {{id: '{file_id}'}})
        RETURN f
        """
        
        result = self.graph.query(query)
        
        if result.result_set:
            file_node = result.result_set[0][0]
            return {
                "file_id": file_node.properties.get('id'),
                "original_filename": file_node.properties.get('original_filename'),
                "stored_filename": file_node.properties.get('stored_filename'),
                "file_path": file_node.properties.get('file_path'),
                "file_size": file_node.properties.get('file_size'),
                "content_type": file_node.properties.get('content_type'),
                "user_id": file_node.properties.get('user_id'),
                "description": file_node.properties.get('description'),
                "upload_timestamp": file_node.properties.get('upload_timestamp')
            }
        
        return None
    
    def delete_file(self, file_id: str) -> None:
        """Delete file and its associated data from database"""
        # Delete file node and its relationships
        query = f"""
        MATCH (f:File {{id: '{file_id}'}})
        OPTIONAL MATCH (f)-[r]-()
        DELETE r, f
        """
        
        self.graph.query(query)
    
    def store_message(self, content: str, role: str, user_id: str, file_id: str = None) -> Dict[str, Any]:
        """Store a message in the database with optional file association"""
        message_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Create message node based on role
        if role.lower() == "agent":
            query = f"""
            MERGE (a:Agent {{id: '{user_id}'}})
            CREATE (m:Message {{id: '{message_id}', content: '{content}', role: '{role}', user_id: '{user_id}', timestamp: '{timestamp}'}})
            CREATE (a)-[:SENT]->(m)
            """
        else:
            query = f"""
            MERGE (u:User {{id: '{user_id}'}})
            CREATE (m:Message {{id: '{message_id}', content: '{content}', role: '{role}', user_id: '{user_id}', timestamp: '{timestamp}'}})
            CREATE (u)-[:SENT]->(m)
            """
        
        # Add file association if file_id is provided
        if file_id:
            query += f"""
            WITH m
            MATCH (f:File {{id: '{file_id}'}})
            CREATE (m)-[:EXTRACTED_FROM]->(f)
            """
        
        self.graph.query(query)
        
        return {
            "message_id": message_id,
            "content": content,
            "role": role,
            "user_id": user_id,
            "timestamp": timestamp
        }
    
    # Helper Functions for FalkorDB Operations
    
    def add_entity(self, label: str, properties: Dict[str, Any]) -> str:
        """Create a new node with a given label and properties"""
        # Generate a unique ID if not provided
        if 'id' not in properties:
            properties['id'] = str(uuid.uuid4())
        
        # Build CREATE query
        property_strings = []
        for key, value in properties.items():
            if isinstance(value, str):
                property_strings.append(f"{key}: '{value}'")
            else:
                property_strings.append(f"{key}: {value}")
        
        properties_str = ", ".join(property_strings)
        query = f"CREATE (n:{label} {{{properties_str}}}) RETURN n.id as id"
        
        try:
            result = self.graph.query(query)
            if result.result_set:
                return result.result_set[0][0]
            return properties['id']
        except Exception as e:
            print(f"Error creating entity: {e}")
            return None
    
    def get_entity_by_id(self, entity_id: str) -> Dict[str, Any]:
        """Fetch a node by its internal id"""
        query = f"MATCH (n) WHERE n.id = '{entity_id}' RETURN n"
        
        try:
            result = self.graph.query(query)
            if result.result_set:
                node = result.result_set[0][0]
                return {
                    "id": node.properties.get('id'),
                    "labels": list(node.labels),
                    "properties": dict(node.properties)
                }
            return None
        except Exception as e:
            print(f"Error fetching entity: {e}")
            return None
    
    def update_entity_property(self, entity_id: str, key: str, value: Any) -> bool:
        """Update a single property (fact) on a node"""
        if isinstance(value, str):
            query = f"MATCH (n) WHERE n.id = '{entity_id}' SET n.{key} = '{value}' RETURN n"
        else:
            query = f"MATCH (n) WHERE n.id = '{entity_id}' SET n.{key} = {value} RETURN n"
        
        try:
            result = self.graph.query(query)
            return len(result.result_set) > 0
        except Exception as e:
            print(f"Error updating entity property: {e}")
            return False
    
    def delete_entity(self, entity_id: str) -> bool:
        """Delete a node (and optionally its relationships)"""
        query = f"""
        MATCH (n) WHERE n.id = '{entity_id}'
        OPTIONAL MATCH (n)-[r]-()
        DELETE r, n
        """
        
        try:
            self.graph.query(query)
            return True
        except Exception as e:
            print(f"Error deleting entity: {e}")
            return False
    
    def create_relationship(self, src_id: str, rel_type: str, dst_id: str) -> bool:
        """Create a relationship between two nodes"""
        query = f"""
        MATCH (src) WHERE src.id = '{src_id}'
        MATCH (dst) WHERE dst.id = '{dst_id}'
        CREATE (src)-[r:{rel_type}]->(dst)
        RETURN r
        """
        
        try:
            result = self.graph.query(query)
            return len(result.result_set) > 0
        except Exception as e:
            print(f"Error creating relationship: {e}")
            return False
    
    def get_neighbors(self, entity_id: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Get all connected nodes within a given depth"""
        if depth == 1:
            query = f"""
            MATCH (n)-[r]-(neighbor) 
            WHERE n.id = '{entity_id}'
            RETURN DISTINCT neighbor, type(r) as relationship_type
            """
        else:
            query = f"""
            MATCH (n)-[r*1..{depth}]-(neighbor) 
            WHERE n.id = '{entity_id}'
            RETURN DISTINCT neighbor, type(r[0]) as relationship_type
            """
        
        try:
            result = self.graph.query(query)
            neighbors = []
            for record in result.result_set:
                neighbor_node = record[0]
                relationship_type = record[1]
                neighbors.append({
                    "id": neighbor_node.properties.get('id'),
                    "labels": list(neighbor_node.labels),
                    "properties": dict(neighbor_node.properties),
                    "relationship_type": relationship_type
                })
            return neighbors
        except Exception as e:
            print(f"Error getting neighbors: {e}")
            return []
    
    def insert_summary(self, session_id: str, summary_text: str) -> str:
        """Create a Summary node linked to a session"""
        summary_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        query = f"""
        MERGE (s:Session {{id: '{session_id}'}})
        CREATE (sum:Summary {{id: '{summary_id}', text: '{summary_text}', timestamp: '{timestamp}'}})
        CREATE (s)-[:HAS_SUMMARY]->(sum)
        RETURN sum.id as id
        """
        
        try:
            result = self.graph.query(query)
            if result.result_set:
                return result.result_set[0][0]
            return summary_id
        except Exception as e:
            print(f"Error inserting summary: {e}")
            return None
    
    def get_session_context(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all nodes/messages linked to a session"""
        query = f"""
        MATCH (s:Session {{id: '{session_id}'}})-[r]-(related)
        RETURN related, type(r) as relationship_type
        """
        
        try:
            result = self.graph.query(query)
            context = []
            for record in result.result_set:
                node = record[0]
                relationship_type = record[1]
                context.append({
                    "id": node.properties.get('id'),
                    "labels": list(node.labels),
                    "properties": dict(node.properties),
                    "relationship_type": relationship_type
                })
            return context
        except Exception as e:
            print(f"Error getting session context: {e}")
            return []
    
    def search_entities_by_property(self, label: str, key: str, value: Any) -> List[Dict[str, Any]]:
        """Find nodes by property filter"""
        if isinstance(value, str):
            query = f"MATCH (n:{label}) WHERE n.{key} = '{value}' RETURN n"
        else:
            query = f"MATCH (n:{label}) WHERE n.{key} = {value} RETURN n"
        
        try:
            result = self.graph.query(query)
            entities = []
            for record in result.result_set:
                node = record[0]
                entities.append({
                    "id": node.properties.get('id'),
                    "labels": list(node.labels),
                    "properties": dict(node.properties)
                })
            return entities
        except Exception as e:
            print(f"Error searching entities: {e}")
            return []
    
    def update_fact_conflict_resolution(self, entity_id: str, key: str, new_value: Any) -> bool:
        """Update fact with conflict resolution - adds timestamp and version info"""
        timestamp = datetime.now().isoformat()
        version_key = f"{key}_version"
        timestamp_key = f"{key}_timestamp"
        
        # Get current version
        current_entity = self.get_entity_by_id(entity_id)
        if not current_entity:
            return False
        
        current_version = current_entity['properties'].get(version_key, 0)
        new_version = current_version + 1
        
        # Update with version and timestamp
        updates = [
            (key, new_value),
            (version_key, new_version),
            (timestamp_key, timestamp)
        ]
        
        try:
            for update_key, update_value in updates:
                self.update_entity_property(entity_id, update_key, update_value)
            return True
        except Exception as e:
            print(f"Error updating fact with conflict resolution: {e}")
            return False
    

