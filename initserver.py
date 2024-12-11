import socket
import os
import subprocess
import time
import json

def get_address():
    """Retrieve the IPv4 address of the active network interface."""
    try:
        hostname = socket.gethostname()
        local_address = socket.gethostbyname(hostname)

        if local_address.startswith("127."):
            # use socket lib to look at available interfaces
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.168.0.1", 80))
                local_address = s.getsockname()[0]
        return local_address
    except Exception as e:
        print(f"Error getting IPV4 address: {e}")
        return None


def update_env(local_address):
    """Update the .env file with the provided IPv4 and callback URL."""
    env_file_path = ".env"
    db_url = f'DATABASE_URL="postgresql://safariconnect:1Amodung%40%21.@{local_address}:5432/safaridb"\n'
    #cb_url = f'CALLBACK_URL="{ngrok_link}/payment/mpesa/callback"\n'
    #ngrok = f'NGROK_URL="{ngrok_link}"\n'
    ipv4_ip = f'IPV4_CURRENT="http://{local_address}:8000"\n'

    if not os.path.exists(env_file_path):
        with open(env_file_path, 'w') as env_file:
            env_file.writelines([db_url])
        return

    with open(env_file_path, 'r') as env_file:
        lines = env_file.readlines()

    with open(env_file_path, 'w') as env_file:
        for line in lines:
            if line.startswith('DATABASE_URL'):
                env_file.write(db_url)
            elif line.startswith('IPV4_CURRENT'):
                env_file.write(ipv4_ip)
            else:
                env_file.write(line)
        if not any(line.startswith('IPV4_CURRENT') for line in lines):
            env_file.write(ipv4_ip)

def start_server(local_address):
    """Start the server using Uvicorn."""
    process = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    )
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping server...")
        process.terminate()
        process.wait()

if __name__ == "__main__":
    ipv4 = get_address()

    if ipv4:
        print(f"IPv4: {ipv4}")
        update_env(ipv4)
        start_server(ipv4)
    else:
        print("Failed to retrieve IP address or ngrok URL.")

