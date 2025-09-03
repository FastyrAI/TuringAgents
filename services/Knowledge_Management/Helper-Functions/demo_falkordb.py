#!/usr/bin/env python3
"""
Simple demo script for FalkorDB helper functions
This shows basic usage examples
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from FalkorDB.database import DatabaseManager

def demo_basic_operations():
    """Demonstrate basic operations"""
    print("🚀 FalkorDB Helper Functions Demo")
    print("=" * 40)
    
    try:
        # Initialize database
        db = DatabaseManager()
        print("✅ Connected to FalkorDB")
        
        # Demo 1: Create entities
        print("\n📝 Creating entities...")
        user_id = db.add_entity("User", {
            "name": "Alice",
            "email": "alice@example.com",
            "role": "developer"
        })
        print(f"   Created user: {user_id}")
        
        project_id = db.add_entity("Project", {
            "name": "AI Assistant",
            "status": "active",
            "budget": 50000
        })
        print(f"   Created project: {project_id}")
        
        # Demo 2: Create relationships
        print("\n🔗 Creating relationships...")
        db.create_relationship(user_id, "WORKS_ON", project_id)
        print("   User works on project")
        
        # Demo 3: Get entities
        print("\n🔍 Retrieving entities...")
        user = db.get_entity_by_id(user_id)
        project = db.get_entity_by_id(project_id)
        
        print(f"   User: {user['properties']['name']} - {user['properties']['role']}")
        print(f"   Project: {project['properties']['name']} - ${project['properties']['budget']}")
        
        # Demo 4: Get neighbors
        print("\n👥 Getting neighbors...")
        neighbors = db.get_neighbors(user_id)
        print(f"   User has {len(neighbors)} connections")
        
        # Demo 5: Update properties
        print("\n✏️ Updating properties...")
        db.update_entity_property(user_id, "role", "senior developer")
        print("   Updated user role")
        
        # Demo 6: Search
        print("\n🔎 Searching entities...")
        developers = db.search_entities_by_property("User", "role", "senior developer")
        print(f"   Found {len(developers)} senior developers")
        
        # Demo 7: Cleanup
        print("\n🧹 Cleaning up...")
        db.delete_entity(user_id)
        db.delete_entity(project_id)
        print("   Demo data cleaned up")
        
        print("\n✅ Demo completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure FalkorDB is running and configured properly")

if __name__ == "__main__":
    demo_basic_operations()
