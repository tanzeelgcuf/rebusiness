from database_manager import DatabaseManager
db = DatabaseManager()
# Initialization triggers create_tables() which includes the drop/create logic we added
print("Schema updated successfully.")
