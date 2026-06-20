# pyrefly: ignore [missing-import]
from pymongo import MongoClient

# Connect to the MongoDB instance
client = MongoClient("mongodb://localhost:27017/")

# Drop the entire database
client.drop_database("energy_ai_db")

print("Database 'energy_ai_db' has been completely cleared!")
