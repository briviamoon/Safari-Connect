import secrets

# Generate a 32-byte hex key for strong security
secret_key = secrets.token_hex(32)
print(secret_key)
