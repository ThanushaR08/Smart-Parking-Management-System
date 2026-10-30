from database.db import db, slots

print("Current Database:", db.name)

slots.delete_many({})

for i in range(1, 51):
    slots.insert_one({
        "slot_number": f"B{i:03}",
        "vehicle_type": "Bike",
        "status": "Available"
    })

for i in range(1, 51):
    slots.insert_one({
        "slot_number": f"C{i:03}",
        "vehicle_type": "Car",
        "status": "Available"
    })

print("Total Slots:", slots.count_documents({}))
print("100 Parking Slots Created Successfully!")