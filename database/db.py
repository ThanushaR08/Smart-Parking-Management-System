from pymongo import MongoClient
from config import Config


client = MongoClient(Config.MONGO_URI)


db = client[Config.DATABASE_NAME]

print("Database Name:", db.name)
print("Collections:", db.list_collection_names())

users = db["users"]

slots = db["slots"]

bookings = db["bookings"]

payments = db["payments"]

admins = db["admins"]

# ---------------- CREATE DEFAULT SLOTS ----------------

if slots.count_documents({}) == 0:

    slot_data = []

    # Create 50 Car Slots
    for i in range(1, 51):

        slot_data.append({

            "slot_number": f"C{i:03}",

            "vehicle_type": "Car",

            "status": "Available"

        })

    # Create 50 Bike Slots
    for i in range(1, 51):

        slot_data.append({

            "slot_number": f"B{i:03}",

            "vehicle_type": "Bike",

            "status": "Available"

        })

    slots.insert_many(slot_data)

    print("✅ 100 Parking Slots Created Successfully")