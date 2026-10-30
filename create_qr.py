import qrcode

# Replace with your own UPI ID
upi_id = "yourupiid@upi"

# Parking amount
amount = "100"

# UPI Payment Link
payment_link = (
    f"upi://pay?pa={upi_id}"
    f"&pn=Smart Parking System"
    f"&am={amount}"
    f"&cu=INR"
)

# Generate QR Code
qr = qrcode.make(payment_link)

# Save QR Code
qr.save("static/images/payment_qr.png")


print("QR Code Created Successfully!")