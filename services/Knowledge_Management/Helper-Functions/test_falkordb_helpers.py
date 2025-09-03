#!/usr/bin/env python3
"""
Test script for FalkorDB helper functions
Run this script to test all the helper functions in your DatabaseManager class
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from FalkorDB.database import DatabaseManager

def test_all_helpers():
    """Test all FalkorDB helper functions"""
    
    print("Starting FalkorDB Helper Functions Test")
    print("=" * 50)
    
    try:
        # Initialize database manager
        print("Connecting to FalkorDB...")
        db = DatabaseManager()
        print("Connected successfully!")
        
        # Test 1: Add Entity
        print("\nTest 1: Adding Entities")
        print("-" * 30)
        
        # Add a User entity
        user_props = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "created_at": datetime.now().isoformat()
        }
        user_id = db.add_entity("User", user_props)
        print(f"Created User entity with ID: {user_id}")
        
        # Add a Product entity
        product_props = {
            "name": "Laptop",
            "price": 999.99,
            "category": "Electronics",
            "in_stock": True
        }
        product_id = db.add_entity("Product", product_props)
        print(f"Created Product entity with ID: {product_id}")
        
        # Test 2: Get Entity by ID
        print("\nTest 2: Getting Entity by ID")
        print("-" * 30)
        
        user_entity = db.get_entity_by_id(user_id)
        if user_entity:
            print(f"Retrieved User: {user_entity['properties']['name']}")
            print(f"   Labels: {user_entity['labels']}")
            print(f"   Properties: {user_entity['properties']}")
        
        # Test 3: Update Entity Property
        print("\nTest 3: Updating Entity Properties")
        print("-" * 30)
        
        success = db.update_entity_property(user_id, "age", 31)
        if success:
            print("Updated user age to 31")
        
        # Update product price
        success = db.update_entity_property(product_id, "price", 1099.99)
        if success:
            print("Updated product price to $1099.99")
        
        # Test 4: Create Relationships
        print("\nTest 4: Creating Relationships")
        print("-" * 30)
        
        # Create relationship: User PURCHASED Product
        success = db.create_relationship(user_id, "PURCHASED", product_id)
        if success:
            print("Created PURCHASED relationship between User and Product")
        
        # Test 5: Get Neighbors
        print("\nTest 5: Getting Neighbors")
        print("-" * 30)
        
        neighbors = db.get_neighbors(user_id, depth=1)
        print(f"Found {len(neighbors)} neighbors for User:")
        for neighbor in neighbors:
            print(f"   - {neighbor['labels'][0]}: {neighbor['properties'].get('name', 'N/A')}")
        
        # Test 6: Insert Summary
        print("\nTest 6: Inserting Summary")
        print("-" * 30)
        
        session_id = "test_session_123"
        summary_text = "User John Doe purchased a laptop for $1099.99"
        summary_id = db.insert_summary(session_id, summary_text)
        if summary_id:
            print(f"Created Summary with ID: {summary_id}")
        
        # Test 7: Get Session Context
        print("\nTest 7: Getting Session Context")
        print("-" * 30)
        
        session_context = db.get_session_context(session_id)
        print(f"Found {len(session_context)} items in session context:")
        for item in session_context:
            print(f"   - {item['labels'][0]}: {item['properties'].get('text', item['properties'].get('name', 'N/A'))}")
        
        # Test 8: Search Entities by Property
        print("\nTest 8: Searching Entities by Property")
        print("-" * 30)
        
        # Search for users by age
        users_by_age = db.search_entities_by_property("User", "age", 31)
        print(f"Found {len(users_by_age)} users with age 31")
        
        # Search for products by category
        products_by_category = db.search_entities_by_property("Product", "category", "Electronics")
        print(f"Found {len(products_by_category)} products in Electronics category")
        
        # Test 9: Update Fact with Conflict Resolution
        print("\nTest 9: Updating Fact with Conflict Resolution")
        print("-" * 30)
        
        success = db.update_fact_conflict_resolution(user_id, "email", "john.doe@example.com")
        if success:
            print("Updated email with conflict resolution (version tracking)")
        
        # Test 10: Get Updated Entity
        print("\nTest 10: Getting Updated Entity")
        print("-" * 30)
        
        updated_user = db.get_entity_by_id(user_id)
        if updated_user:
            print("Updated User properties:")
            for key, value in updated_user['properties'].items():
                print(f"   {key}: {value}")
        
        print("\nAll tests completed successfully!")
        print("=" * 50)
        
        # Cleanup (optional - comment out if you want to keep test data)
        print("\nCleaning up test data...")
        db.delete_entity(user_id)
        db.delete_entity(product_id)
        print("Test data cleaned up")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

def test_individual_functions():
    """Test individual helper functions one by one"""
    
    print("\nIndividual Function Testing")
    print("=" * 50)
    
    try:
        db = DatabaseManager()
        
        # Test add_entity
        print("\n1️⃣ Testing add_entity...")
        test_entity = db.add_entity("TestEntity", {"name": "Test", "value": 42})
        print(f"   Result: {test_entity}")
        
        # Test get_entity_by_id
        print("\n2️⃣ Testing get_entity_by_id...")
        retrieved = db.get_entity_by_id(test_entity)
        print(f"   Result: {retrieved is not None}")
        
        # Test update_entity_property
        print("\n3️⃣ Testing update_entity_property...")
        updated = db.update_entity_property(test_entity, "value", 100)
        print(f"   Result: {updated}")
        
        # Test create_relationship
        print("\n4️⃣ Testing create_relationship...")
        second_entity = db.add_entity("SecondEntity", {"name": "Second"})
        relationship = db.create_relationship(test_entity, "CONNECTS_TO", second_entity)
        print(f"   Result: {relationship}")
        
        # Test get_neighbors
        print("\n5️⃣ Testing get_neighbors...")
        neighbors = db.get_neighbors(test_entity)
        print(f"   Result: {len(neighbors)} neighbors found")
        
        # Cleanup
        db.delete_entity(test_entity)
        db.delete_entity(second_entity)
        
    except Exception as e:
        print(f"Error in individual testing: {e}")

if __name__ == "__main__":
    print("FalkorDB Helper Functions Test Suite")
    print("Make sure you have:")
    print("1. FalkorDB running and accessible")
    print("2. Proper environment variables set in .env file")
    print("3. Required Python packages installed")
    print()
    
    # Run comprehensive test
    test_all_helpers()
    
    # Run individual function tests
    test_individual_functions()
    
    print("\n Testing complete!")
