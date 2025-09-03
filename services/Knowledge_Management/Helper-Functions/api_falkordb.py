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


if __name__ == "__main__":
    print("API documentation available at: http://localhost:8001/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
