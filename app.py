from datetime import datetime, timedelta
import easyocr
import qrcode
from flask_mail import Mail, Message
from reportlab.pdfgen import canvas
import cv2
from ultralytics import YOLO
from flask import Response
from io import BytesIO
import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
)
from bson.objectid import ObjectId
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
 
from database.db import (
    db,
    users,
    slots,
    bookings,
    payments,
    admins
)
from config import Config

# ==========================
# OVERSTAY SETTINGS
# ==========================

OVERSTAY_LIMIT_HOURS = 5
OVERSTAY_LIMIT_MINUTES = 3

app = Flask(__name__)

app.config.from_object(Config)
mail = Mail(app)

camera = cv2.VideoCapture(0)
model = YOLO("yolov8n.pt")

app.secret_key = Config.SECRET_KEY
def send_receipt_email(payment, pdf_bytes):

    msg = Message(
        subject="Smart Parking Payment Receipt",
        recipients=[payment["email"]]
    )

    msg.body = f"""
Hello {payment['name']},

Your payment has been completed successfully.

===============================
SMART PARKING SYSTEM
===============================

Customer Name : {payment['name']}
Email         : {payment['email']}
Mobile        : {payment['mobile']}

Vehicle No    : {payment['vehicle_number']}
Vehicle Type  : {payment['vehicle_type']}
Parking Slot  : {payment['slot_number']}

Amount Paid   : ₹{payment['amount']}
Payment Status: Paid

Thank you for using Smart Parking System.

Your payment receipt is attached with this email.

Regards,
Smart Parking Team
"""

    msg.attach(
        "Parking_Receipt.pdf",
        "application/pdf",
        pdf_bytes
    )

    try:
        mail.send(msg)
        print("✅ Receipt email sent successfully.")

    except Exception as e:
        print("❌ Email sending failed:", e)


# ---------------- HOME ----------------


@app.route("/")
def home():
    return render_template("website.html")

@app.route("/login")
def login():
    return render_template("index.html")

#-----------website-----------
@app.route("/website")
def website():
    return render_template("website.html")


# ---------------- ADMIN LOGIN PAGE ----------------

@app.route("/admin")
def admin():

    return render_template("admin_login.html")


# ---------------- REGISTER PAGE ----------------

@app.route("/register")
def register():

    return render_template("register.html")

#----------------ABOUT--------------------
@app.route("/about")
def about():
    return render_template("about.html")

#-----------SERVICES-------------------

@app.route("/services")
def services():

  return render_template("services.html")

@app.route("/slot_booking")
def slot_booking():

    if "user" not in session:
        return redirect(url_for("login"))

    car_slots = list(
        slots.find({"vehicle_type": "Car"}).sort("slot_number", 1)
    )

    bike_slots = list(
        slots.find({"vehicle_type": "Bike"}).sort("slot_number", 1)
    )

    today = datetime.now().strftime("%Y-%m-%d")

    return render_template(
        "slot_booking.html",
        car_slots=car_slots,
        bike_slots=bike_slots,
        today=today
    )


#--------------CONTACT-------------------

@app.route("/contact")
def contact():
    return render_template("contact.html")


# ---------------- REGISTER USER ----------------

@app.route("/register_user", methods=["POST"])
def register_user():

    name = request.form.get("name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    vehicle_type = request.form.get("vehicle_type")
    vehicle_number = request.form.get("vehicle_number")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")


    # Check empty fields
    if not name or not email or not password:

        flash("Please fill all required fields")

        return redirect(url_for("register"))



    # Check password match

    if password != confirm_password:

        flash("Passwords do not match")

        return redirect(url_for("register"))



    # Check existing email

    existing_user = users.find_one(
        {
            "email": email
        }
    )


    if existing_user:

        flash("Email already registered")

        return redirect(url_for("register"))



    # Password encryption

    hashed_password = generate_password_hash(
        password,
        method="pbkdf2:sha256"
    )



    # Store user data in MongoDB

    users.insert_one({

        "name": name,

        "email": email,

        "mobile": mobile,

        "vehicle_type": vehicle_type,

        "vehicle_number": vehicle_number,

        "password": hashed_password

    })



    flash("Registration Successful. Please Login")


    return redirect(
        url_for("home")
    )



# ---------------- LOGIN USER ----------------

@app.route("/login_user", methods=["POST"])
def login_user():

    email = request.form.get("email")
    password = request.form.get("password")

    user = users.find_one({
        "email": email
    })

    if not user:

        flash("Invalid Email")
        return redirect(url_for("home"))

    if not check_password_hash(user["password"], password):

        flash("Invalid Password")
        return redirect(url_for("home"))

    session["user"] = user["name"]
    session["email"] = user["email"]

    print(session)   # Optional: for debugging

    flash("Login Successful")
    return redirect(url_for("dashboard"))


# ---------------- ADMIN LOGIN ----------------
@app.route("/admin_login", methods=["POST"])
def admin_login():

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    print("=" * 40)
    print("Database:", db.name)
    print("Entered Username:", username)

    print("All admins in database:")
    for a in admins.find():
        print(a)

    admin = admins.find_one({"username": username})

    print("Found Admin:", admin)
    print("=" * 40)

    if admin is None:
        flash("Admin not found")
        return redirect(url_for("admin"))

    if admin["password"] != password:
        flash("Wrong Password")
        return redirect(url_for("admin"))

    session["admin"] = admin["name"]

    return redirect(url_for("admin_dashboard"))

# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("home"))

    # Today's date and current time
    today = datetime.now().strftime("%Y-%m-%d")
    current_datetime = datetime.now()
    current_time = current_datetime.strftime("%H:%M")

    # ---------------- AUTO EXPIRE BOOKINGS ----------------

    expired_bookings = bookings.find({
        "booking_date": today,
        "status": "Reserved"
    })

    for booking in expired_bookings:

        booking_datetime = datetime.strptime(
            booking["booking_date"] + " " + booking["expected_entry"],
            "%Y-%m-%d %H:%M"
        )

        # 15 minute grace period
        if current_datetime > booking_datetime + timedelta(minutes=15):

            payments.insert_one({

                "name": booking.get("name", ""),
                "email": booking.get("email", ""),
                "vehicle_number": booking.get("vehicle_number", ""),
                "vehicle_type": booking.get("vehicle_type", ""),
                "slot_number": booking.get("slot_number", ""),
                "booking_date": booking.get("booking_date", ""),
                "entry_time": booking.get("expected_entry", ""),
                "exit_time": booking.get("expected_exit", ""),
                "amount": 0,
                "payment_status": "Booking Expired"

            })

            bookings.delete_one({
                "_id": booking["_id"]
            })

    # ---------------- AUTO START BOOKINGS ----------------

    bookings.update_many(

        {
            "booking_date": today,
            "expected_entry": {
                "$lte": current_time
            },
            "status": "Reserved"
        },

        {
            "$set": {
                "status": "Active"
            }
        }

    )

    # ---------------- GET LOGGED-IN USER ----------------

    user = users.find_one({
        "email": session["email"]
    })

    if not user:
        flash("User not found.")
        return redirect(url_for("home"))

    # ---------------- LOAD SLOTS ----------------

    if user["vehicle_type"] == "Car":

        car_slots = list(
            slots.find({"vehicle_type": "Car"}).sort("slot_number", 1)
        )

        bike_slots = []

    else:

        bike_slots = list(
            slots.find({"vehicle_type": "Bike"}).sort("slot_number", 1)
        )

        car_slots = []

    # ---------------- TODAY BOOKINGS ----------------

    today_bookings = list(

        bookings.find(

            {
                "booking_date": today,
                "status": {
                    "$in": [
                        "Reserved",
                        "Active"
                    ]
                }
            }

        )

    )

    booked_slots = []

    for book in today_bookings:
        booked_slots.append(book["slot_number"])

    # ---------------- UPDATE SLOT COLOUR ----------------

    for slot in car_slots:

        if slot["slot_number"] in booked_slots:
            slot["status"] = "Reserved"
        else:
            slot["status"] = "Available"

    for slot in bike_slots:

        if slot["slot_number"] in booked_slots:
            slot["status"] = "Reserved"
        else:
            slot["status"] = "Available"

    # ---------------- CURRENT USER BOOKING ----------------

    booking = bookings.find_one(

        {
            "email": session["email"],
            "status": {
                "$in": [
                    "Reserved",
                    "Active"
                ]
            }
        }

    )

    print("Current Booking:", booking)

    # ---------------- CHECK EXTRA TIME ----------------

    extra_time = False

    if booking and booking["status"] == "Active":

        try:

            now = datetime.now()

            exit_datetime = datetime.strptime(
                booking["booking_date"] + " " + booking["expected_exit"],
                "%Y-%m-%d %H:%M"
            )

            if now > exit_datetime:
                extra_time = True

        except Exception as e:
            print("Extra Time Error:", e)

    # ---------------- SHOW PAGE ----------------

    return render_template(

        "dashboard.html",

        name=session.get("user"),

        bike_slots=bike_slots,

        car_slots=car_slots,

        booking=booking,

        today=today,

        booked_slots=booked_slots,

        extra_time=extra_time

    )


# ---------------- BOOK SLOT ----------------

@app.route("/book_slot", methods=["POST"])
def book_slot():

    if "user" not in session:
        return redirect(url_for("home"))

    slot_number = request.form.get("slot_number")
    booking_date = request.form.get("booking_date")
    entry_time = request.form.get("entry_time")
    exit_time = request.form.get("exit_time")

    # ---------------- DATE VALIDATION ----------------

    today = datetime.now().date()

    selected_date = datetime.strptime(
        booking_date,
        "%Y-%m-%d"
    ).date()

    if selected_date < today:

        flash("You cannot book a parking slot for a past date.")

        return redirect(url_for("dashboard"))

    # ---------------- TIME VALIDATION ----------------

    current_time = datetime.now().strftime("%H:%M")

    if booking_date == today.strftime("%Y-%m-%d"):

        if entry_time <= current_time:

            flash("Please select a future entry time.")

            return redirect(url_for("dashboard"))

    # ---------------- TIME FORMAT VALIDATION ----------------

    new_start = datetime.strptime(
        entry_time,
        "%H:%M"
    )

    new_end = datetime.strptime(
        exit_time,
        "%H:%M"
    )

    if new_end <= new_start:

        flash("Exit time must be after Entry time.")

        return redirect(url_for("dashboard"))

    # ---------------- CHECK USER ALREADY HAS BOOKING ----------------

    my_booking = bookings.find_one({

        "email": session["email"],

        "status": {
            "$in": [
                "Reserved",
                "Active"
            ]
        }

    })

    if my_booking:

        flash("You already have an active booking.")

        return redirect(url_for("dashboard"))

    # ---------------- CHECK SLOT OVERLAP ----------------

    existing_bookings = bookings.find({

        "slot_number": slot_number,

        "booking_date": booking_date,

        "status": {
            "$in": [
                "Reserved",
                "Active"
            ]
        }

    })

    for booking in existing_bookings:

        old_start = datetime.strptime(
            booking["expected_entry"],
            "%H:%M"
        )

        old_end = datetime.strptime(
            booking["expected_exit"],
            "%H:%M"
        )

        if new_start < old_end and new_end > old_start:

            flash(

                f"Slot {slot_number} is already booked from "

                f"{booking['expected_entry']} to "

                f"{booking['expected_exit']}"

            )

            return redirect(url_for("dashboard"))

    # ---------------- GET USER DETAILS ----------------

    user = users.find_one({

        "email": session["email"]

    })

    if not user:

        flash("User not found.")

        return redirect(url_for("dashboard"))



    # ---------------- CHECK SLOT EXISTS ----------------

    slot = slots.find_one({
        "slot_number": slot_number
    })

    if not slot:
        flash("Invalid parking slot.")
        return redirect(url_for("dashboard"))

    # Car cannot book Bike
    # Bike cannot book Car

    if slot["vehicle_type"] != user["vehicle_type"]:
      flash("Please select the correct parking slot.")
      return redirect(url_for("dashboard"))

    if slot["status"] != "Available":
        flash("This parking slot is already booked.")
        return redirect(url_for("dashboard"))
    # ---------------- CHECK VEHICLE TYPE ----------------

    if user["vehicle_type"] != slot["vehicle_type"]:
        flash(
            f"You registered a {user['vehicle_type']}. "
            f"You can only book {user['vehicle_type']} slots."
        )
        return redirect(url_for("dashboard"))


    # ---------------- SAVE BOOKING ----------------

    bookings.insert_one({

        "name": user["name"],

        "email": user["email"],

        "mobile": user["mobile"],

        "vehicle_number": user["vehicle_number"],

        "vehicle_type": user["vehicle_type"],

        "slot_number": slot_number,

        "booking_date": booking_date,

        "expected_entry": entry_time,

        "expected_exit": exit_time,

        "entry_time": None,

        "status": "Reserved"

    })

    # ---------------- UPDATE SLOT STATUS ----------------

    slots.update_one(

        {
            "slot_number": slot_number
        },

        {
            "$set": {
                "status": "Reserved"
            }
        }

    )

    flash("Parking slot booked successfully.")

    return redirect(url_for("dashboard"))
# ---------------- CANCEL BOOKING ----------------

@app.route("/cancel_booking")
def cancel_booking():

    if "user" not in session:
        return redirect(url_for("home"))


    booking = bookings.find_one({

    "email": session["email"],

    "status":
    {
        "$in":
        [
            "Reserved",
            "Active"
        ]
    }

})

    if not booking:

        flash("No booking found to cancel")

        return redirect(url_for("dashboard"))



    # Store cancellation history

    payments.insert_one({

        "name": booking["name"],

        "email": booking["email"],

        "mobile": booking["mobile"],

        "vehicle_number": booking["vehicle_number"],

        "vehicle_type": booking["vehicle_type"],

        "slot_number": booking["slot_number"],

        "booking_date": booking["booking_date"],

        "entry_time": booking["expected_entry"],

        "exit_time": booking["expected_exit"],

        "amount": 0,

        "payment_status": "Cancelled"

    })


    # Make slot available again

    slots.update_one(

    {
        "slot_number": booking["slot_number"]
    },

    {
        "$set": {
            "status": "Available"
        }
    }

) 
    




    # Remove active reservation

    bookings.delete_one({

        "_id": booking["_id"]

    })



    flash("Booking cancelled successfully")

    return redirect(url_for("dashboard"))

# ---------------- START PARKING ----------------

@app.route("/start_parking")
def start_parking():

    if "user" not in session:
        return redirect(url_for("home"))


    booking = bookings.find_one({

        "email": session["email"],

        "status":
        {
            "$in":
            [
                "Reserved",
                "Active"
            ]
        }

    })


    if not booking:

        flash("No booking found")

        return redirect(url_for("dashboard"))



    bookings.update_one(

        {
            "_id": booking["_id"]
        },

        {
            "$set":
            {
                "entry_time": datetime.now(),

                "status": "Active"
            }
        }

    )


    flash("Parking Started Successfully")

    return redirect(url_for("dashboard"))



# ---------------- EXIT PARKING / BILL ----------------

@app.route("/exit_parking")
def exit_parking():

    if "user" not in session:
        return redirect(url_for("home"))

    booking = bookings.find_one({
        "email": session["email"],
        "status": {
            "$in": ["Reserved", "Active"]
        }
    })

    if not booking:
        flash("No Active Booking Found")
        return redirect(url_for("dashboard"))

    exit_time = datetime.now()

    entry_time = booking.get("entry_time")

    if not entry_time:
        flash("Please start parking before exit")
        return redirect(url_for("dashboard"))

    total_minutes = int(
        (exit_time - entry_time).total_seconds() / 60
    )

    hours = total_minutes // 60
    minutes = total_minutes % 60

    receipt_id = "PK" + datetime.now().strftime("%Y%m%d%H%M%S")

    if total_minutes <= 0:
        amount = 0
        payment_status = "No Payment Required"
    else:
        amount = (hours * 20) + (minutes * 5)

        if amount == 0:
            payment_status = "No Payment Required"
        else:
            payment_status = "Pending"

    # Save payment history
    payment = {

        "name": booking["name"],
        "email": booking["email"],
        "mobile": booking["mobile"],

        "vehicle_number": booking["vehicle_number"],
        "vehicle_type": booking["vehicle_type"],

        "slot_number": booking["slot_number"],

        "booking_date": booking["booking_date"],
        "payment_date": datetime.now().strftime("%Y-%m-%d"),

        "expected_entry": booking["expected_entry"],
        "expected_exit": booking["expected_exit"],

        "entry_time": booking["entry_time"],
        "exit_time": exit_time,

        "hours": hours,
        "minutes": minutes,

        "amount": amount,
        "payment_status": payment_status,
        "receipt_id": receipt_id

    }

    # Insert payment

    result = payments.insert_one(payment)
    payment_id = result.inserted_id

    # Make slot available
    slots.update_one(
        {
            "slot_number": booking["slot_number"]
        },
        {
            "$set": {
                "status": "Available"
            }
        }
    )

    # Generate UPI QR
    upi_id = "usha@upi"

    payment_link = (
        f"upi://pay?pa={upi_id}"
        f"&pn=Smart Parking System"
        f"&am={amount}"
        f"&cu=INR"
    )

    qr = qrcode.make(payment_link)
    qr.save("static/images/payment_qr.png")

    bill_data = booking.copy()

    # Delete active booking
    bookings.delete_one({
        "_id": booking["_id"]
    })

    # No payment required
    if amount == 0:

        payments.update_one(
            {
                "_id": payment_id
            },
            {
                "$set": {
                    "payment_status": "No Payment Required"
                }
            }
        )

        flash("Parking completed successfully.")

        return redirect(url_for("history"))

    # Show bill page
    return render_template(
        "bill.html",
        booking=bill_data,
        exit_time=exit_time,
        hours=hours,
        minutes=minutes,
        amount=amount
    )
# ---------------- PAYMENT STATUS ----------------
@app.route("/payment/<status>")
def payment(status):

    if "user" not in session:
        return redirect(url_for("home"))

    latest_payment = payments.find_one(
{
       "email": session["email"]
    },
    sort=[("_id",-1)]
)

    if not latest_payment:
        flash("No payment record found")
        return redirect(url_for("dashboard"))

    if status == "success":

        if latest_payment["amount"] > 0:

            # Update payment status
            payments.update_one(
                {
                    "_id": latest_payment["_id"]
                },
                {
                    "$set": {
                        "payment_status": "Paid"
                    }
                }
            )

            # Get updated payment
            payment = payments.find_one(
                {
                    "_id": latest_payment["_id"]
                }
            )

            # Create PDF in memory
            pdf = BytesIO()

            receipt = canvas.Canvas(pdf)

            receipt.setTitle("Parking Receipt")

            receipt.setFont("Helvetica-Bold", 18)
            receipt.drawCentredString(300, 800, "SMART PARKING SYSTEM")

            receipt.setFont("Helvetica", 12)

            receipt.drawString(50, 760, f"Customer Name : {payment['name']}")
            receipt.drawString(50, 740, f"Email : {payment['email']}")
            receipt.drawString(50, 720, f"Mobile : {payment['mobile']}")

            receipt.drawString(50, 690, f"Vehicle Number : {payment['vehicle_number']}")
            receipt.drawString(50, 670, f"Vehicle Type : {payment['vehicle_type']}")
            receipt.drawString(50, 650, f"Parking Slot : {payment['slot_number']}")

            receipt.drawString(50, 620, f"Amount Paid : ₹{payment['amount']}")
            receipt.drawString(50, 600, "Payment Status : Paid")

            receipt.drawString(50, 560, "Thank you for using Smart Parking System.")

            receipt.save()
            pdf.seek(0)

            # Send receipt email
            send_receipt_email(
                payment,
                pdf.read()
            )

            return render_template("payment_success.html")

        else:

            payments.update_one(
                {
                    "_id": latest_payment["_id"]
                },
                {
                    "$set": {
                        "payment_status": "No Payment Required"
                    }
                }
            )

            return redirect(url_for("history"))

    else:

        payments.update_one(
            {
                "_id": latest_payment["_id"]
            },
            {
                "$set": {
                    "payment_status": "Failed"
                }
            }
        )

        return render_template("payment_failed.html")



# ---------------- HISTORY ----------------


@app.route("/history")
def history():

    if "user" not in session:
        return redirect(url_for("home"))

    print("Logged in Email:", session["email"])

    # Get ONLY the latest paid transaction of this user
    payment = payments.find_one(
        {
            "email": session["email"],
            "payment_status": "Paid"
        },
        sort=[("_id", -1)]
    )

    payment_history = []

    if payment:
        payment_history.append(payment)

    return render_template(
        "history.html",
        payment_history=payment_history
    )

# ---------------- DOWNLOAD INVOICE ----------------

@app.route("/download_invoice/<payment_id>")
def download_invoice(payment_id):

    if "user" not in session:
        return redirect(url_for("home"))

    payment = payments.find_one(
        {"_id": ObjectId(payment_id)}
    )

    if not payment:
        flash("Invoice not found")
        return redirect(url_for("history"))

    pdf = BytesIO()

    receipt = canvas.Canvas(pdf)

    receipt.setTitle("Parking Receipt")

    receipt.setFont("Helvetica-Bold",18)
    receipt.drawString(180,800,"SMART PARKING SYSTEM")

    receipt.setFont("Helvetica",12)

    receipt.drawString(50,760,f"Customer Name : {payment.get('name','')}")
    receipt.drawString(50,740,f"Email : {payment.get('email','')}")
    receipt.drawString(50,720,f"Mobile : {payment.get('mobile','')}")

    receipt.drawString(50,690,f"Vehicle Number : {payment.get('vehicle_number','')}")
    receipt.drawString(50,670,f"Vehicle Type : {payment.get('vehicle_type','')}")
    receipt.drawString(50,650,f"Parking Slot : {payment.get('slot_number','')}")

    receipt.drawString(50,620,f"Amount Paid : ₹{payment.get('amount',0)}")
    receipt.drawString(50,600,f"Payment Status : {payment.get('payment_status','')}")

    receipt.save()

    pdf.seek(0)

    return send_file(
        pdf,
        as_attachment=True,
        download_name="Parking_Receipt.pdf",
        mimetype="application/pdf"
    )




# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect(url_for("admin_login"))


    total_users = users.count_documents({})

    total_slots = slots.count_documents({})


    available_slots = slots.count_documents({
        "status":"Available"
    })

    occupied_slots = slots.count_documents({
    "status":"Reserved"
})


    active_parking = bookings.count_documents({
        "status":"Active"
    })


    total_revenue = sum(
        payment.get("amount",0)
        for payment in payments.find()
    )


    payment_data = list(
        payments.find()
        .sort("_id",-1)
        .limit(5)
    )
    

    return render_template(
        "admin_dashboard.html",

        total_users=total_users,
        total_slots=total_slots,
        available_slots=available_slots,
        occupied_slots=occupied_slots,
        active_parking=active_parking,
        total_revenue=total_revenue,
        payments=payment_data
    )
# ---------------- ADMIN USERS ----------------
@app.route("/admin_users")
def admin_users():

    if "admin" not in session:
        return redirect(url_for("admin"))

    search = request.args.get("search", "").strip()

    if search:

        all_users = list(

            users.find({

                "$or": [

                    {
                        "name": {
                            "$regex": search,
                            "$options": "i"
                        }
                    },

                    {
                        "email": {
                            "$regex": search,
                            "$options": "i"
                        }
                    },

                    {
                        "mobile": {
                            "$regex": search,
                            "$options": "i"
                        }
                    },

                    {
                        "vehicle_number": {
                            "$regex": search,
                            "$options": "i"
                        }
                    }

                ]

            })

        )

    else:

        all_users = list(users.find())

    return render_template(

        "admin_users.html",

        users=all_users

    )
# ---------------- DELETE USER ----------------

@app.route("/delete_user/<email>")
def delete_user(email):

    if "admin" not in session:

        return redirect(url_for("admin"))

    users.delete_one({

        "email": email

    })

    flash("User Deleted Successfully")

    return redirect(url_for("admin_users"))

# ---------------- ADMIN BOOKINGS ----------------
@app.route("/admin_bookings")
def admin_bookings():

    if "admin" not in session:
        return redirect(url_for("admin"))

    all_bookings = list(bookings.find())

    print("TOTAL BOOKINGS:", len(all_bookings))

    for b in all_bookings:
        print(b)

    return render_template(
        "admin_bookings.html",
        bookings=all_bookings
    )

# ---------------- ADMIN CANCEL BOOKING ----------------

@app.route("/admin_cancel_booking/<id>")
def admin_cancel_booking(id):

    if "admin" not in session:

        return redirect(url_for("admin"))

    booking = bookings.find_one({

        "_id": ObjectId(id)

    })

    print("BOOKING DATA:")
    print(booking)
    if booking:

        # Make slot available again
        slots.update_one(

            {
                "slot_number": booking["slot_number"]
            },

            {
                "$set":{
                    "status":"Available"
                }
            }

        )

        # Store cancellation in payment history
        payments.insert_one({
            "name": booking.get("name", ""),

            "email": booking.get("email", ""),

            "mobile": booking.get("mobile", ""),

            "vehicle_number": booking.get("vehicle_number", ""),

            "vehicle_type": booking.get("vehicle_type", ""),

            "slot_number": booking.get("slot_number", ""),

            "booking_date": booking.get("booking_date", ""),

            "entry_time": booking.get("expected_entry", ""),

            "exit_time": booking.get("expected_exit", ""),

            "amount": 0,
            
            "payment_status": "Cancelled"

        })

        bookings.delete_one({

            "_id": ObjectId(id)

        })

        flash("Booking Cancelled Successfully")

    return redirect(url_for("admin_bookings"))

# ---------------- ADMIN SLOTS ----------------

@app.route("/admin_slots")
def admin_slots():

    if "admin" not in session:
        return redirect(url_for("admin"))

    all_slots = list(slots.find().sort("slot_number",1))

    return render_template(
        "admin_slots.html",
        slots=all_slots
    )


# ---------------- ADMIN PAYMENTS ----------------

@app.route("/admin_payments")
def admin_payments():

    if "admin" not in session:
        return redirect(url_for("admin_login"))


    status = request.args.get("status")


    query = {}


    if status and status != "All":
        query["payment_status"] = status



    payment_data = list(
        payments.find(query).sort("_id",-1)
    )



    total_revenue = sum(

        payment.get("amount",0)

        for payment in payment_data

        if payment.get("payment_status") == "Paid"

    )



    return render_template(
        "admin_payments.html",
        payments=payment_data,
        total_revenue=total_revenue
    )
# ---------------- ADMIN LOGOUT ----------------

@app.route("/admin_logout")
def admin_logout():

    session.pop("admin", None)

    flash("Admin Logged Out")

    return redirect(url_for("website"))


# ---------------- LOGOUT ----------------


@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out successfully")

    return redirect(url_for("home"))







# ---------------- DATABASE TEST ----------------

@app.route("/test-db")
def test_db():

    try:
        db.command("ping")
        return "MongoDB Connected Successfully!"

    except Exception as e:
        return f"Database Connection Failed: {e}"


# ---------------- ADMIN TEST ----------------
@app.route("/test_admin")
def test_admin():

    print("Database:", db.name)

    print("Collections:", db.list_collection_names())

    print("Admins Collection:")

    for admin in admins.find():
        print(admin)

    return "Check Terminal"

#----------------DOWNLOAD INVOICE-----------

def generate_frames():

    while True:

        success, frame = camera.read()

        if not success:
            break

        results = model(frame)

        annotated = results[0].plot()

        ret, buffer = cv2.imencode('.jpg', annotated)

        frame = buffer.tobytes()

    yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               frame + b'\r\n')



print("Registered Routes:")
print(app.url_map)

def generate_frames():

    while True:

        success, frame = camera.read()

        if not success:
            break

        results = model(frame)

        annotated = results[0].plot()

        ret, buffer = cv2.imencode(".jpg", annotated)

        frame = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame +
            b'\r\n'
        )

@app.route("/video_feed")
def video_feed():

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/camera")
def camera_page():

    return render_template("camera.html")


@app.route("/capture_vehicle", methods=["POST"])
def capture_vehicle():

    return "Vehicle Captured Successfully!"



if __name__ == "__main__":
    app.run(debug=True)
    print(app.url_map)