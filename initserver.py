import socket
import os
import subprocess
import time
import json

def getAddress():
    """Retrieve the IPv4 address of the active network interface."""
    try:
        hostname = socket.gethostname()
        ipv4 = socket.gethostbyname(hostname)

        if ipv4.startswith("127."):
            # use socket lib to look at avilable interfacesa
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.168.0.1", 80))
                ipv4 = s.getsockname()[0]
        return ipv4
    except Exception as e:
        print(f"Error getting IPV4 address: {e}")
        return None


def update_env(ipv4, ngrok_url):
    """Update the .env file with the provided IPv4 and callback URL."""
    env_file_path = ".env"
    db_url = f'DATABASE_URL="postgresql://safariconnect:1Amodung%40%21.@{ipv4}:5432/safaridb"\n'
    cb_url = f'CALLBACK_URL="{ngrok_url}/payment/mpesa/callback"\n'
    ngrok = f'NGROK_URL="{ngrok_url}"\n'
    ipv4_ip = f'IPV4_CURRENT="http://{ipv4}:8000"\n'

    if not os.path.exists(env_file_path):
        with open(env_file_path, 'w') as env_file:
            env_file.writelines([db_url, cb_url, ngrok])
        return

    with open(env_file_path, 'r') as env_file:
        lines = env_file.readlines()

    updated = False
    with open(env_file_path, 'w') as env_file:
        for line in lines:
            if line.startswith('DATABASE_URL'):
                env_file.write(db_url)
                updated = True
            elif line.startswith('CALLBACK_URL'):
                env_file.write(cb_url)
                updated = True
            elif line.startswith('NGROK_URL'):
                env_file.write(ngrok)
                updated = True
            elif line.startswith('IPV4_CURRENT'):
                env_file.write(ipv4_ip)
                updated = True
            else:
                env_file.write(line)
                
        if not any(line.startswith('NGROK_URL') for line in lines):
            env_file.write(ngrok)
        elif not any(line.startswith('IPV4_CURRENT') for line in lines):
            env_file.write(ipv4_ip)

def get_ngrok_url():
    """Start ngrok and retrieve the public URL."""
    try:
        process = subprocess.Popen(['ngrok', 'http', '8000'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(10):  # Wait up to 10 seconds for ngrok to start
            time.sleep(1)
            output, error = subprocess.Popen(
                ['curl', '--silent', 'http://localhost:4040/api/tunnels'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ).communicate()
            if output:
                try:
                    tunnels = json.loads(output.decode('utf-8'))
                    for tunnel in tunnels.get("tunnels", []):
                        if "http" in tunnel["public_url"]:
                            process.terminate()  # Clean up ngrok process
                            return tunnel["public_url"]
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error parsing ngrok response: {e}")
        process.terminate()
        print("Timeout waiting for ngrok.")
        return None
    except Exception as e:
        print(f"Error starting ngrok: {e}")
        return None

def start_server(ipv4):
    """Start the server using Uvicorn."""
    process = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", ipv4, "--port", "8000", "--reload"]
    )
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping server...")
        process.terminate()
        process.wait()

if __name__ == "__main__":
    ipv4 = getAddress()
    ngrok_url = get_ngrok_url()

    if ipv4 and ngrok_url:
        print(f"IPv4: {ipv4}")
        print(f"ngrok: {ngrok_url}")
        update_env(ipv4, ngrok_url)
        start_server(ipv4)
    else:
        print("Failed to retrieve IP address or ngrok URL.")

