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
    
    
    def add_agent(self, agent_id: str, role: str, meta: Dict[str, Any] = None) -> str:
        """Create an Agent node (e.g., Planner, Retriever, Summarizer) with metadata"""
        if meta is None:
            meta = {}
        
        properties = {
            "id": agent_id,
            "role": role,
            "created_at": datetime.now().isoformat(),
            **meta
        }
        
        return self.add_entity("Agent", properties)
    
    def link_agent_to_session(self, agent_id: str, session_id: str) -> bool:
        """Record which agent worked on which session"""
        return self.create_relationship(agent_id, "WORKED_ON", session_id)
    
    def store_event(self, session_id: str, event_type: str, details: Dict[str, Any]) -> str:
        """Insert an Event node (e.g., action taken, system output) linked to a session"""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Convert details to JSON string to avoid Cypher syntax issues
        import json
        details_json = json.dumps(details)
        
        properties = {
            "id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "details": details_json
        }
        
        # Create event node
        event_node_id = self.add_entity("Event", properties)
        
        # Link to session
        if event_node_id:
            self.create_relationship(session_id, "HAS_EVENT", event_node_id)
        
        return event_node_id
    
    def get_context_window(self, session_id: str, n: int = 10) -> List[Dict[str, Any]]:
        """Retrieve the last n messages/entities for rolling context windows"""
        query = f"""
        MATCH (s:Session {{id: '{session_id}'}})-[r]-(related)
        RETURN related, type(r) as relationship_type, r.timestamp as rel_timestamp
        ORDER BY rel_timestamp DESC
        LIMIT {n}
        """
        
        try:
            result = self.graph.query(query)
            context = []
            for record in result.result_set:
                node = record[0]
                relationship_type = record[1]
                timestamp = record[2] if len(record) > 2 else None
                context.append({
                    "id": node.properties.get('id'),
                    "labels": list(node.labels),
                    "properties": dict(node.properties),
                    "relationship_type": relationship_type,
                    "timestamp": timestamp
                })
            return context
        except Exception as e:
            print(f"Error getting context window: {e}")
            return []
    
    def get_summary_for_session(self, session_id: str, latest_only: bool = True) -> List[Dict[str, Any]]:
        """Retrieve summaries linked to a session"""
        if latest_only:
            query = f"""
            MATCH (s:Session {{id: '{session_id}'}})-[:HAS_SUMMARY]->(sum:Summary)
            RETURN sum
            ORDER BY sum.timestamp DESC
            LIMIT 1
            """
        else:
            query = f"""
            MATCH (s:Session {{id: '{session_id}'}})-[:HAS_SUMMARY]->(sum:Summary)
            RETURN sum
            ORDER BY sum.timestamp DESC
            """
        
        try:
            result = self.graph.query(query)
            summaries = []
            for record in result.result_set:
                node = record[0]
                summaries.append({
                    "id": node.properties.get('id'),
                    "text": node.properties.get('text'),
                    "timestamp": node.properties.get('timestamp')
                })
            return summaries
        except Exception as e:
            print(f"Error getting summaries: {e}")
            return []
    
    def upsert_fact(self, entity_id: str, key: str, value: Any, provenance: str) -> bool:
        """Add/update a fact while attaching provenance info"""
        timestamp = datetime.now().isoformat()
        provenance_key = f"{key}_provenance"
        timestamp_key = f"{key}_timestamp"
        
        try:
            # Update the fact
            self.update_entity_property(entity_id, key, value)
            # Add provenance
            self.update_entity_property(entity_id, provenance_key, provenance)
            # Add timestamp
            self.update_entity_property(entity_id, timestamp_key, timestamp)
            return True
        except Exception as e:
            print(f"Error upserting fact: {e}")
            return False
    
    def create_context_summary(self, session_id: str, method: str = "map_reduce") -> str:
        """Generate a Summary node and link it to a session"""
        summary_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Get context for summary
        context = self.get_context_window(session_id, 20)
        
        # Apply summarization method
        summary_text = self._apply_summarization_method(context, method)
        
        properties = {
            "id": summary_id,
            "text": summary_text,
            "method": method,
            "timestamp": timestamp,
            "item_count": len(context)
        }
        
        # Create summary node
        summary_node_id = self.add_entity("Summary", properties)
        
        # Link to session
        if summary_node_id:
            self.create_relationship(session_id, "HAS_SUMMARY", summary_node_id)
        
        return summary_node_id
    
    def checkpoint_context(self, session_id: str, checkpoint_tag: str) -> str:
        """Store a checkpoint node linked to all current session facts/messages"""
        checkpoint_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Get current context
        context = self.get_session_context(session_id)
        
        properties = {
            "id": checkpoint_id,
            "checkpoint_tag": checkpoint_tag,
            "timestamp": timestamp,
            "context_size": len(context)
        }
        
        # Create checkpoint node
        checkpoint_node_id = self.add_entity("Checkpoint", properties)
        
        # Link to session
        if checkpoint_node_id:
            self.create_relationship(session_id, "HAS_CHECKPOINT", checkpoint_node_id)
        
        return checkpoint_node_id
    
    def compress_context(self, session_id: str, target_size: int) -> str:
        """Store a reduced set of entities/messages as a compressed snapshot"""
        compressed_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Get context and select key nodes (simplified selection)
        context = self.get_session_context(session_id)
        key_nodes = context[:target_size] if len(context) > target_size else context
        
        properties = {
            "id": compressed_id,
            "original_size": len(context),
            "compressed_size": len(key_nodes),
            "compression_ratio": len(key_nodes) / len(context) if context else 0,
            "timestamp": timestamp
        }
        
        # Create compressed node
        compressed_node_id = self.add_entity("Compressed", properties)
        
        # Link to session
        if compressed_node_id:
            self.create_relationship(session_id, "HAS_COMPRESSED", compressed_node_id)
        
        return compressed_node_id
    
    def trace_reasoning_path(self, start_id: str, end_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """Extract the reasoning chain (path of relationships) between two nodes"""
        query = f"""
        MATCH path = (start)-[*1..{max_depth}]-(end)
        WHERE start.id = '{start_id}' AND end.id = '{end_id}'
        RETURN path, length(path) as path_length
        ORDER BY path_length
        LIMIT 1
        """
        
        try:
            result = self.graph.query(query)
            if result.result_set:
                path_record = result.result_set[0]
                path = path_record[0]
                path_length = path_record[1]
                
                # Extract nodes and relationships from path
                reasoning_chain = []
                
                # Try different ways to access path data based on FalkorDB version
                try:
                    # Method 1: Direct iteration over path
                    path_items = list(path)
                    for item in path_items:
                        if hasattr(item, 'labels'):  # It's a node
                            reasoning_chain.append({
                                "type": "node",
                                "id": item.properties.get('id'),
                                "labels": list(item.labels),
                                "properties": dict(item.properties)
                            })
                        elif hasattr(item, 'type'):  # It's a relationship
                            reasoning_chain.append({
                                "type": "relationship",
                                "relationship_type": item.type,
                                "properties": dict(item.properties) if item.properties else {}
                            })
                except:
                    try:
                        # Method 2: Access nodes and relationships separately
                        nodes = list(path.nodes()) if hasattr(path, 'nodes') else []
                        relationships = list(path.relationships()) if hasattr(path, 'relationships') else []
                        
                        for i in range(len(nodes)):
                            node = nodes[i]
                            reasoning_chain.append({
                                "type": "node",
                                "id": node.properties.get('id'),
                                "labels": list(node.labels),
                                "properties": dict(node.properties)
                            })
                            
                            if i < len(relationships):
                                rel = relationships[i]
                                reasoning_chain.append({
                                    "type": "relationship",
                                    "relationship_type": rel.type,
                                    "properties": dict(rel.properties) if rel.properties else {}
                                })
                    except:
                        # Method 3: Fallback - return basic path info
                        reasoning_chain.append({
                            "type": "path_info",
                            "message": "Path found but unable to extract detailed structure",
                            "path_length": path_length
                        })
                
                return {
                    "path": reasoning_chain,
                    "length": path_length,
                    "found": True
                }
            else:
                return {"path": [], "length": 0, "found": False}
        except Exception as e:
            print(f"Error tracing reasoning path: {e}")
            return {"path": [], "length": 0, "found": False, "error": str(e)}
    
    
    def fetch_entity_by_property(self, label: str, property_key: str, property_value: Any) -> Dict[str, Any]:
        """Retrieve an entity by a specific property (e.g., fetch a user by their email or id)"""
        if isinstance(property_value, str):
            query = f"MATCH (n:{label}) WHERE n.{property_key} = '{property_value}' RETURN n LIMIT 1"
        else:
            query = f"MATCH (n:{label}) WHERE n.{property_key} = {property_value} RETURN n LIMIT 1"
        
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
            print(f"Error fetching entity by property: {e}")
            return None
    
    def get_all_entities_of_type(self, label: str) -> List[Dict[str, Any]]:
        """Retrieve all entities of a given type/label"""
        query = f"MATCH (n:{label}) RETURN n"
        
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
            print(f"Error getting all entities of type: {e}")
            return []
    
    def get_relationships_by_type(self, entity_id: str, relationship_type: str) -> List[Dict[str, Any]]:
        """Retrieve relationships of a specific type linked to an entity"""
        query = f"""
        MATCH (n)-[r:{relationship_type}]-(related)
        WHERE n.id = '{entity_id}'
        RETURN r, related, type(r) as rel_type
        """
        
        try:
            result = self.graph.query(query)
            relationships = []
            for record in result.result_set:
                rel = record[0]
                related_node = record[1]
                rel_type = record[2]
                relationships.append({
                    "relationship": {
                        "type": rel_type,
                        "properties": dict(rel.properties) if rel.properties else {}
                    },
                    "related_entity": {
                        "id": related_node.properties.get('id'),
                        "labels": list(related_node.labels),
                        "properties": dict(related_node.properties)
                    }
                })
            return relationships
        except Exception as e:
            print(f"Error getting relationships by type: {e}")
            return []
    
    def get_message_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve a history of messages exchanged within a session"""
        # Find messages from users/agents who participate in the session
        query = f"""
        MATCH (s:Session {{id: '{session_id}'}})<-[:PARTICIPATES_IN]-(participant)-[:SENT]->(m:Message)
        RETURN m
        ORDER BY m.timestamp ASC
        """
        
        try:
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
        except Exception as e:
            print(f"Error getting message history: {e}")
            return []
    
    def get_all_messages_by_role(self, role: str, session_id: str = None) -> List[Dict[str, Any]]:
        """Retrieve messages of a specific role (e.g., only the agent's or user's messages)"""
        if session_id:
            query = f"""
            MATCH (s:Session {{id: '{session_id}'}})-[:HAS_MESSAGE]->(m:Message)
            WHERE m.role = '{role}'
            RETURN m
            ORDER BY m.timestamp ASC
            """
        else:
            query = f"""
            MATCH (m:Message)
            WHERE m.role = '{role}'
            RETURN m
            ORDER BY m.timestamp ASC
            """
        
        try:
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
        except Exception as e:
            print(f"Error getting messages by role: {e}")
            return []
    
    def remove_relationships_between_entities(self, entity1_id: str, entity2_id: str, relationship_type: str) -> bool:
        """Remove all relationships of a specific type between two entities"""
        query = f"""
        MATCH (n1)-[r:{relationship_type}]-(n2)
        WHERE n1.id = '{entity1_id}' AND n2.id = '{entity2_id}'
        DELETE r
        """
        
        try:
            self.graph.query(query)
            return True
        except Exception as e:
            print(f"Error removing relationships: {e}")
            return False
    
    def add_user_to_session(self, user_id: str, session_id: str) -> bool:
        """Associate a user with a session, typically when a new user joins the session"""
        query = f"""
        MERGE (u:User {{id: '{user_id}'}})
        MERGE (s:Session {{id: '{session_id}'}})
        CREATE (u)-[:PARTICIPATES_IN]->(s)
        """
        
        try:
            self.graph.query(query)
            return True
        except Exception as e:
            print(f"Error adding user to session: {e}")
            return False
    
    def archive_context(self, session_id: str, archive_type: str = "session") -> str:
        """Archive the current session or task's context into a separate archival node for later reference"""
        archive_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Get current context
        context = self.get_session_context(session_id)
        
        # Convert context to JSON for storage with proper escaping
        import json
        try:
            # Clean the context data to avoid JSON issues
            cleaned_context = []
            for item in context:
                cleaned_item = {}
                for key, value in item.items():
                    if isinstance(value, str):
                        # Check if the string is already JSON and needs special handling
                        if key == "details" and value.startswith("{") and value.endswith("}"):
                            try:
                                # Try to parse and re-serialize the JSON string to ensure it's valid
                                parsed_details = json.loads(value)
                                cleaned_item[key] = json.dumps(parsed_details, ensure_ascii=False)
                            except json.JSONDecodeError:
                                # If it's not valid JSON, escape it normally
                                cleaned_item[key] = value.replace("'", "\\'").replace('"', '\\"')
                        else:
                            # Escape any problematic characters for regular strings
                            cleaned_item[key] = value.replace("'", "\\'").replace('"', '\\"')
                    else:
                        cleaned_item[key] = value
                cleaned_context.append(cleaned_item)
            
            context_json = json.dumps(cleaned_context, default=str, ensure_ascii=False)
        except Exception as e:
            print(f"Error serializing context to JSON: {e}")
            context_json = "[]"
        
        properties = {
            "id": archive_id,
            "archive_type": archive_type,
            "original_session_id": session_id,
            "context_data": context_json,
            "context_size": len(context),
            "archived_at": timestamp
        }
        
        # Create archive node
        archive_node_id = self.add_entity("Archive", properties)
        
        # Link to original session
        if archive_node_id:
            self.create_relationship(session_id, "ARCHIVED_AS", archive_node_id)
        
        return archive_node_id
    
    def get_context_from_archive(self, archive_id: str) -> Dict[str, Any]:
        """Retrieve archived context (such as a session snapshot) for analysis or review"""
        query = f"""
        MATCH (a:Archive {{id: '{archive_id}'}})
        RETURN a
        """
        
        try:
            result = self.graph.query(query)
            if result.result_set:
                archive_node = result.result_set[0][0]
                import json
                
                # Get the context_data string
                context_data_str = archive_node.properties.get('context_data', '[]')
                
                # Try to parse JSON, with fallback for malformed JSON
                try:
                    context_data = json.loads(context_data_str)
                except json.JSONDecodeError as json_err:
                    pass
                    
                    # Try to fix common JSON issues in archived data
                    try:
                        # Safe approach: manually parse and reconstruct the JSON
                        import re
                        
                        # Extract individual objects from the array
                        # Find all objects between { and } that are at the top level
                        objects = []
                        brace_count = 0
                        current_obj = ""
                        in_string = False
                        escape_next = False
                        
                        for i, char in enumerate(context_data_str):
                            if escape_next:
                                escape_next = False
                                current_obj += char
                                continue
                                
                            if char == '\\':
                                escape_next = True
                                current_obj += char
                                continue
                                
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                current_obj += char
                                continue
                                
                            if not in_string:
                                if char == '{':
                                    if brace_count == 0:
                                        current_obj = char
                                    else:
                                        current_obj += char
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    current_obj += char
                                    if brace_count == 0:
                                        objects.append(current_obj)
                                        current_obj = ""
                                else:
                                    if brace_count > 0:
                                        current_obj += char
                            else:
                                if brace_count > 0:
                                    current_obj += char
                        
                        # Process each object to fix the details field
                        fixed_objects = []
                        for obj in objects:
                            try:
                                # Try to parse the object as-is first
                                parsed_obj = json.loads(obj)
                                fixed_objects.append(parsed_obj)
                            except json.JSONDecodeError:
                                # Fix the details field in this object
                                fixed_obj = obj
                                
                                # Find and fix details fields with unescaped JSON
                                def fix_details_in_object(match):
                                    full_match = match.group(0)
                                    details_value = match.group(1)
                                    
                                    # Escape quotes in the JSON content
                                    escaped_value = details_value.replace('"', '\\"')
                                    return f'"details": "{escaped_value}"'
                                
                                # Pattern to match "details": "{"...":"..."}"
                                details_pattern = r'"details":\s*"(\{[^}]*\})"'
                                fixed_obj = re.sub(details_pattern, fix_details_in_object, fixed_obj)
                                
                                try:
                                    parsed_obj = json.loads(fixed_obj)
                                    fixed_objects.append(parsed_obj)
                                except json.JSONDecodeError:
                                    # If still can't parse, skip this object
                                    print(f"Skipping malformed object in archive {archive_id}")
                                    continue
                        
                        context_data = fixed_objects
                        print(f"Successfully fixed and parsed {len(context_data)} objects for archive {archive_id}")
                        
                    except Exception as fix_err:
                        print(f"Could not fix JSON for archive {archive_id}: {fix_err}")
                        # Return empty list as final fallback
                        context_data = []
                
                return {
                    "archive_id": archive_node.properties.get('id'),
                    "archive_type": archive_node.properties.get('archive_type'),
                    "original_session_id": archive_node.properties.get('original_session_id'),
                    "context_data": context_data,
                    "context_size": archive_node.properties.get('context_size'),
                    "archived_at": archive_node.properties.get('archived_at')
                }
            return None
        except Exception as e:
            print(f"Error getting context from archive: {e}")
            return None
    
    def fetch_context_at_checkpoint(self, session_id: str, checkpoint_tag: str) -> Dict[str, Any]:
        """Retrieve context data from a specific checkpoint in the session"""
        query = f"""
        MATCH (s:Session {{id: '{session_id}'}})-[:HAS_CHECKPOINT]->(c:Checkpoint {{checkpoint_tag: '{checkpoint_tag}'}})
        RETURN c
        ORDER BY c.timestamp DESC
        LIMIT 1
        """
        
        try:
            result = self.graph.query(query)
            if result.result_set:
                checkpoint_node = result.result_set[0][0]
                return {
                    "checkpoint_id": checkpoint_node.properties.get('id'),
                    "checkpoint_tag": checkpoint_node.properties.get('checkpoint_tag'),
                    "timestamp": checkpoint_node.properties.get('timestamp'),
                    "context_size": checkpoint_node.properties.get('context_size')
                }
            return None
        except Exception as e:
            print(f"Error fetching context at checkpoint: {e}")
            return None
    
    def get_event_log_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve events linked to a session (actions, updates, etc.)"""
        query = f"""
        MATCH (s:Session {{id: '{session_id}'}})-[:HAS_EVENT]->(e:Event)
        RETURN e
        ORDER BY e.timestamp ASC
        """
        
        try:
            result = self.graph.query(query)
            events = []
            for record in result.result_set:
                event = record[0]
                import json
                details = json.loads(event.properties.get('details', '{}'))
                events.append({
                    "event_id": event.properties.get('id'),
                    "event_type": event.properties.get('event_type'),
                    "timestamp": event.properties.get('timestamp'),
                    "details": details
                })
            return events
        except Exception as e:
            print(f"Error getting event log for session: {e}")
            return []


