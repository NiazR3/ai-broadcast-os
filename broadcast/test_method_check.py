import sys
sys.path.insert(0, '.')

from agents.persona_repository import PersonaRepository

# Create an instance and check what methods it has
repo = PersonaRepository()
methods = [method for method in dir(repo) if not method.startswith('_')]
print("Available methods:", methods)

# Check specifically for duplicate method exists
print("Has duplicate method:", hasattr(repo, 'duplicate'))
if hasattr(repo, 'duplicate'):
    print("Duplicate method:", getattr(repo, 'duplicate'))
else:
    print("Duplicate method NOT FOUND")