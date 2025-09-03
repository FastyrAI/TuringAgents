#!/usr/bin/env python3
"""
Check if all required packages are installed for FalkorDB
"""

def check_packages():
    """Check required packages"""
    print("🔍 Checking required packages...")
    
    required_packages = [
        "falkordb",
        "uuid",
        "datetime",
        "typing"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == "uuid":
                import uuid
            elif package == "datetime":
                import datetime
            elif package == "typing":
                import typing
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - MISSING")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Install them with: pip install " + " ".join(missing_packages))
    else:
        print("\n✅ All required packages are installed!")

def check_environment():
    """Check environment variables"""
    print("\n🔍 Checking environment variables...")
    
    import os
    
    # Load environment variables from config
    try:
        from config import FALKORDB_HOST, FALKORDB_PORT, FALKORDB_USERNAME, FALKORDB_PASSWORD, FALKORDB_GRAPH_NAME
        
        env_vars = [
            ("FALKORDB_HOST", FALKORDB_HOST),
            ("FALKORDB_PORT", FALKORDB_PORT),
            ("FALKORDB_USERNAME", FALKORDB_USERNAME),
            ("FALKORDB_PASSWORD", FALKORDB_PASSWORD),
            ("FALKORDB_GRAPH_NAME", FALKORDB_GRAPH_NAME)
        ]
        
        missing_env = []
        
        for var_name, var_value in env_vars:
            if var_value is not None:
                # Mask password for security
                if var_name == "FALKORDB_PASSWORD":
                    display_value = "***" if var_value else "NOT SET"
                else:
                    display_value = str(var_value)
                print(f"✅ {var_name}: {display_value}")
            else:
                print(f"❌ {var_name}: NOT SET")
                missing_env.append(var_name)
        
        if missing_env:
            print(f"\n⚠️  Missing environment variables: {', '.join(missing_env)}")
            print("Create a .env file with these variables")
        else:
            print("\n✅ All environment variables are set!")
            
    except ImportError as e:
        print(f"❌ Error importing config: {e}")
        print("Make sure config.py exists and is properly configured")
    except Exception as e:
        print(f"❌ Error checking environment: {e}")

if __name__ == "__main__":
    print("FalkorDB Requirements Checker")
    print("=" * 40)
    
    check_packages()
    check_environment()
    
    print("\n📋 Next steps:")
    print("1. Make sure FalkorDB is running")
    print("2. Set up your .env file")
    print("3. Run: python demo_falkordb.py")
    print("4. Or run: python test_falkordb_helpers.py")
