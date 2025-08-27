import falkordb
import uuid
from datetime import datetime
from typing import List, Dict, Any
from config import *

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
        match_queries = []
        
        for query_data in queries:
            query = query_data["query"].strip()
            if query.upper().startswith("MERGE"):
                merge_queries.append(query_data)
            else:
                match_queries.append(query_data)
        
        # Execute MERGE queries first
        for query_data in merge_queries:
            try:
                self.graph.query(query_data["query"])
            except Exception as e:
                print(f"Error executing MERGE query: {e}")
        
        # Execute MATCH queries after
        for query_data in match_queries:
            try:
                self.graph.query(query_data["query"])
            except Exception as e:
                print(f"Error executing MATCH query: {e}")
    
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
