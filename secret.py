import secrets

def secretKey():
    secret= secrets.token_hex(64)
    print(f"{secret}\n")

secretKey()