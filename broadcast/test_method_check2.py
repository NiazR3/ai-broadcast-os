import sys
import os
print("Current directory:", os.getcwd())
print("Python path:", sys.path)

# Add the current directory to the path
sys.path.insert(0, '.')

try:
    from agents.persona_repository import PersonaRepository
    print("Import successful!")

    # Create an instance and check what methods it has
    repo = PersonaRepository()
    methods = [method for method in dir(repo) if not method.startswith('_')]
    print("Available methods:", methods)

    # Check specifically for duplicate method exists
    print("Has duplicate method:", hasattr(repo, 'duplicate'))
    if hasattr(repo, 'duplicate'):
        print("Duplicate method FOUND")
    else:
        print("Duplicate method NOT FOUND")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()