def generate_otp():
    # Generate 6-digit OTP
    import random
    return str(random.randint(100000, 999999))

try:
    otp = generate_otp()
    print(f"OTP GENERATED: {otp}")
except Exception as e:
    print(f"Error generating OTP: {e}")