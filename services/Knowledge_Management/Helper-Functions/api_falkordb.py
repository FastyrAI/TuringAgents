#!/usr/bin/env python3
"""
FastAPI application for FalkorDB helper functions
Run this to test your helper functions in the browser
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uvicorn
from datetime import datetime

# Import your database manager
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from FalkorDB.database import DatabaseManager

# Initialize FastAPI app
app = FastAPI(
    title="FalkorDB Helper Functions API",
    description="API to test all FalkorDB helper functions",
    version="1.0.0"
)

# Initialize database manager
db = DatabaseManager()

# Pydantic models for request/response
class EntityCreate(BaseModel):
    label: str
    properties: Dict[str, Any]

class PropertyUpdate(BaseModel):
    key: str
    value: Any

class RelationshipCreate(BaseModel):
    src_id: str
    rel_type: str
    dst_id: str

class SummaryCreate(BaseModel):
    session_id: str
    summary_text: str

class SearchQuery(BaseModel):
    label: str
    key: str
    value: Any

class FactUpdate(BaseModel):
    key: str
    new_value: Any

# New Pydantic models for advanced functions
class AgentCreate(BaseModel):
    agent_id: str
    role: str
    meta: Dict[str, Any] = {}

class EventCreate(BaseModel):
    session_id: str
    event_type: str
    details: Dict[str, Any]

class UpsertFact(BaseModel):
    key: str
    value: Any
    provenance: str

class ContextSummary(BaseModel):
    session_id: str
    method: str = "map_reduce"

class CheckpointCreate(BaseModel):
    session_id: str
    checkpoint_tag: str

class CompressContext(BaseModel):
    session_id: str
    target_size: int

class ReasoningPath(BaseModel):
    start_id: str
    end_id: str
    max_depth: int = 5

# New Pydantic models for additional helper functions
class EntityPropertySearch(BaseModel):
    label: str
    property_key: str
    property_value: Any

class RelationshipSearch(BaseModel):
    entity_id: str
    relationship_type: str

class MessageRoleSearch(BaseModel):
    role: str
    session_id: Optional[str] = None

class RemoveRelationship(BaseModel):
    entity1_id: str
    entity2_id: str
    relationship_type: str

class UserSessionLink(BaseModel):
    user_id: str
    session_id: str

class ArchiveContext(BaseModel):
    session_id: str
    archive_type: str = "session"

class TaskAssignment(BaseModel):
    task_id: str
    agent_id: str
    task_details: Dict[str, Any] = {}

class RemoveTaskAssignment(BaseModel):
    task_id: str
    agent_id: str


# API Endpoints for all helper functions

@app.post("/add_entity")
async def add_entity(entity: EntityCreate):
    """Add a new entity with label and properties"""
    try:
        entity_id = db.add_entity(entity.label, entity.properties)
        if entity_id:
            return {"success": True, "entity_id": entity_id, "message": f"Entity {entity.label} created successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create entity")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_entity/{entity_id}")
async def get_entity(entity_id: str):
    """Get entity by ID"""
    try:
        entity = db.get_entity_by_id(entity_id)
        if entity:
            return {"success": True, "entity": entity}
        else:
            raise HTTPException(status_code=404, detail="Entity not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_property/{entity_id}")
async def update_property(entity_id: str, update: PropertyUpdate):
    """Update a single property on an entity"""
    try:
        success = db.update_entity_property(entity_id, update.key, update.value)
        if success:
            return {"success": True, "message": f"Property {update.key} updated successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update property")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_relationship")
async def create_relationship(relationship: RelationshipCreate):
    """Create a relationship between two entities"""
    try:
        success = db.create_relationship(relationship.src_id, relationship.rel_type, relationship.dst_id)
        if success:
            return {"success": True, "message": f"Relationship {relationship.rel_type} created successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create relationship")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_neighbors/{entity_id}")
async def get_neighbors(entity_id: str, depth: int = Query(1, ge=1, le=5)):
    """Get neighbors of an entity within specified depth"""
    try:
        neighbors = db.get_neighbors(entity_id, depth)
        return {"success": True, "neighbors": neighbors, "count": len(neighbors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/insert_summary")
async def insert_summary(summary: SummaryCreate):
    """Insert a summary linked to a session"""
    try:
        summary_id = db.insert_summary(summary.session_id, summary.summary_text)
        if summary_id:
            return {"success": True, "summary_id": summary_id, "message": "Summary created successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create summary")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_session_context/{session_id}")
async def get_session_context(session_id: str):
    """Get all nodes/messages linked to a session"""
    try:
        context = db.get_session_context(session_id)
        return {"success": True, "context": context, "count": len(context)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search_entities")
async def search_entities(label: str, key: str, value: str):
    """Search entities by property filter"""
    try:
        # Try to convert value to appropriate type
        try:
            if value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit():
                value = float(value)
        except:
            pass  # Keep as string if conversion fails
        
        entities = db.search_entities_by_property(label, key, value)
        return {"success": True, "entities": entities, "count": len(entities)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_fact/{entity_id}")
async def update_fact(entity_id: str, update: FactUpdate):
    """Update fact with conflict resolution"""
    try:
        success = db.update_fact_conflict_resolution(entity_id, update.key, update.new_value)
        if success:
            return {"success": True, "message": f"Fact {update.key} updated with conflict resolution"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update fact")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_entity/{entity_id}")
async def delete_entity(entity_id: str):
    """Delete an entity and its relationships"""
    try:
        success = db.delete_entity(entity_id)
        if success:
            return {"success": True, "message": "Entity deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete entity")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Advanced Helper Function API Endpoints

@app.post("/add_agent")
async def add_agent(agent: AgentCreate):
    """Create an Agent node (e.g., Planner, Retriever, Summarizer) with metadata"""
    try:
        agent_id = db.add_agent(agent.agent_id, agent.role, agent.meta)
        if agent_id:
            return {"success": True, "agent_id": agent_id, "message": f"Agent {agent.role} created successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create agent")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/link_agent_to_session")
async def link_agent_to_session(agent_id: str, session_id: str):
    """Record which agent worked on which session"""
    try:
        success = db.link_agent_to_session(agent_id, session_id)
        if success:
            return {"success": True, "message": f"Agent {agent_id} linked to session {session_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to link agent to session")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/store_event")
async def store_event(event: EventCreate):
    """Insert an Event node (e.g., action taken, system output) linked to a session"""
    try:
        event_id = db.store_event(event.session_id, event.event_type, event.details)
        if event_id:
            return {"success": True, "event_id": event_id, "message": "Event stored successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to store event")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_context_window/{session_id}")
async def get_context_window(session_id: str, n: int = Query(10, ge=1, le=100)):
    """Retrieve the last n messages/entities for rolling context windows"""
    try:
        context = db.get_context_window(session_id, n)
        return {"success": True, "context": context, "count": len(context)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_summary_for_session/{session_id}")
async def get_summary_for_session(session_id: str, latest_only: bool = Query(True)):
    """Retrieve summaries linked to a session"""
    try:
        summaries = db.get_summary_for_session(session_id, latest_only)
        return {"success": True, "summaries": summaries, "count": len(summaries)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upsert_fact/{entity_id}")
async def upsert_fact(entity_id: str, fact: UpsertFact):
    """Add/update a fact while attaching provenance info"""
    try:
        success = db.upsert_fact(entity_id, fact.key, fact.value, fact.provenance)
        if success:
            return {"success": True, "message": f"Fact {fact.key} upserted with provenance"}
        else:
            raise HTTPException(status_code=500, detail="Failed to upsert fact")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_context_summary")
async def create_context_summary(summary: ContextSummary):
    """Generate a Summary node and link it to a session"""
    try:
        summary_id = db.create_context_summary(summary.session_id, summary.method)
        if summary_id:
            return {"success": True, "summary_id": summary_id, "message": "Context summary created successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create context summary")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/checkpoint_context")
async def checkpoint_context(checkpoint: CheckpointCreate):
    """Store a checkpoint node linked to all current session facts/messages"""
    try:
        checkpoint_id = db.checkpoint_context(checkpoint.session_id, checkpoint.checkpoint_tag)
        if checkpoint_id:
            return {"success": True, "checkpoint_id": checkpoint_id, "message": "Checkpoint created successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create checkpoint")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/compress_context")
async def compress_context(compress: CompressContext):
    """Store a reduced set of entities/messages as a compressed snapshot"""
    try:
        compressed_id = db.compress_context(compress.session_id, compress.target_size)
        if compressed_id:
            return {"success": True, "compressed_id": compressed_id, "message": "Context compressed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to compress context")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trace_reasoning_path")
async def trace_reasoning_path(path: ReasoningPath):
    """Extract the reasoning chain (path of relationships) between two nodes"""
    try:
        result = db.trace_reasoning_path(path.start_id, path.end_id, path.max_depth)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Additional Helper Function API Endpoints

@app.post("/fetch_entity_by_property")
async def fetch_entity_by_property(search: EntityPropertySearch):
    """Retrieve an entity by a specific property (e.g., fetch a user by their email or id)"""
    try:
        entity = db.fetch_entity_by_property(search.label, search.property_key, search.property_value)
        if entity:
            return {"success": True, "entity": entity}
        else:
            raise HTTPException(status_code=404, detail="Entity not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_all_entities_of_type/{label}")
async def get_all_entities_of_type(label: str):
    """Retrieve all entities of a given type/label"""
    try:
        entities = db.get_all_entities_of_type(label)
        return {"success": True, "entities": entities, "count": len(entities)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_relationships_by_type")
async def get_relationships_by_type(search: RelationshipSearch):
    """Retrieve relationships of a specific type linked to an entity"""
    try:
        relationships = db.get_relationships_by_type(search.entity_id, search.relationship_type)
        return {"success": True, "relationships": relationships, "count": len(relationships)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_message_history/{session_id}")
async def get_message_history(session_id: str):
    """Retrieve a history of messages exchanged within a session"""
    try:
        messages = db.get_message_history(session_id)
        return {"success": True, "messages": messages, "count": len(messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_all_messages_by_role")
async def get_all_messages_by_role(search: MessageRoleSearch):
    """Retrieve messages of a specific role (e.g., only the agent's or user's messages)"""
    try:
        messages = db.get_all_messages_by_role(search.role, search.session_id)
        return {"success": True, "messages": messages, "count": len(messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/remove_relationships_between_entities")
async def remove_relationships_between_entities(remove: RemoveRelationship):
    """Remove all relationships of a specific type between two entities"""
    try:
        success = db.remove_relationships_between_entities(remove.entity1_id, remove.entity2_id, remove.relationship_type)
        if success:
            return {"success": True, "message": f"Relationships of type {remove.relationship_type} removed between entities"}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove relationships")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_user_to_session")
async def add_user_to_session(link: UserSessionLink):
    """Associate a user with a session, typically when a new user joins the session"""
    try:
        success = db.add_user_to_session(link.user_id, link.session_id)
        if success:
            return {"success": True, "message": f"User {link.user_id} added to session {link.session_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to add user to session")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/archive_context")
async def archive_context(archive: ArchiveContext):
    """Archive the current session or task's context into a separate archival node for later reference"""
    try:
        archive_id = db.archive_context(archive.session_id, archive.archive_type)
        if archive_id:
            return {"success": True, "archive_id": archive_id, "message": "Context archived successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to archive context")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_context_from_archive/{archive_id}")
async def get_context_from_archive(archive_id: str):
    """Retrieve archived context (such as a session snapshot) for analysis or review"""
    try:
        context = db.get_context_from_archive(archive_id)
        if context:
            return {"success": True, "context": context}
        else:
            raise HTTPException(status_code=404, detail="Archive not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fetch_context_at_checkpoint/{session_id}/{checkpoint_tag}")
async def fetch_context_at_checkpoint(session_id: str, checkpoint_tag: str):
    """Retrieve context data from a specific checkpoint in the session"""
    try:
        context = db.fetch_context_at_checkpoint(session_id, checkpoint_tag)
        if context:
            return {"success": True, "context": context}
        else:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_event_log_for_session/{session_id}")
async def get_event_log_for_session(session_id: str):
    """Retrieve events linked to a session (actions, updates, etc.)"""
    try:
        events = db.get_event_log_for_session(session_id)
        return {"success": True, "events": events, "count": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":

    print(" API documentation available at: http://localhost:8001/docs")
   
    
    uvicorn.run(app, host="0.0.0.0", port=8001)