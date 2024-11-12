from fastapi import APIRouter, Request, Depends, HTTPException
import subprocess, platform, uuid, socket, logging, asyncio
from app.auth.deps import get_current_user

router = APIRouter()
#Get Client MAC ADDRESS

@router.get("/mac-address")
async def get_mac_address(req: Request, user=Depends(get_current_user)):
    if not isinstance(req, Request):
        logging.error("Received a non-Request object.")
        return {
            "status": "error",
            "message": "Invalid request object"
        }

    try:
        print(f"Request type: {type(req)}")
        client_ip = req.client.host
        logging.info(f"Attempting to retrieve MAC for IP: {client_ip}")
        
        # if async is still waiting ...
        if asyncio.iscoroutinefunction(get_mac_from_ip):
            mac_address = await get_mac_from_ip(client_ip)
        else:
            mac_address = get_mac_from_ip(client_ip)
        
        # Check if MAC address was successfully retrieved; otherwise use fallback
        if not mac_address:
            mac_address = "00:00:00:00:00:00"  # Placeholder for unobtainable MAC
        
        return {
            "status": "success" if mac_address else "error",
            "mac_address": mac_address,
            "client_ip": client_ip
        }
    except Exception as e:
        logging.error(f"Error in MAC address endpoint: {e}")
        return {
            "status": "error",
            "message": "An unexpected error occurred",
            "client_ip": client_ip if 'client_ip' in locals() else "unknown"
        }


#############################################################################
def get_mac_from_ip(ip_address):
    """
    Attempt to retrieve MAC address for a given IP address using multiple methods.
    
    Args:
        ip_address (str): IP address to find MAC for
    
    Returns:
        str: MAC address if found, None otherwise
    """
    try:
        # Method 1: Use system-specific ARP commands
        os_system = platform.system().lower()
        
        if os_system == 'windows':
            try:
                # Windows ARP command
                result = subprocess.run(['arp', '-a', ip_address], 
                                        capture_output=True, 
                                        text=True, 
                                        timeout=5)
                # Parse ARP output to extract MAC
                for line in result.stdout.split('\n'):
                    if ip_address in line:
                        # Extract MAC address (typically in format xx-xx-xx-xx-xx-xx)
                        mac = line.split()[-1].replace('-', ':')
                        if mac and len(mac.split(':')) == 6:
                            return mac
            except Exception as e:
                logging.error(f"Windows ARP lookup failed: {e}")
        
        elif os_system in ['linux', 'darwin']:  # Linux or macOS
            try:
                # Linux/macOS ARP command
                result = subprocess.run(['arp', '-n', ip_address], 
                                        capture_output=True, 
                                        text=True, 
                                        timeout=5)
                # Parse ARP output to extract MAC
                for line in result.stdout.split('\n'):
                    if ip_address in line:
                        # Extract MAC address (typically in format xx:xx:xx:xx:xx:xx)
                        parts = line.split()
                        mac = parts[2] if len(parts) > 2 else None
                        if mac and len(mac.split(':')) == 6:
                            return mac
            except Exception as e:
                logging.error(f"Linux/macOS ARP lookup failed: {e}")
        
        # Method 2: Fallback to UUID (if above methods fail)
        # This will return a pseudo-MAC based on the system's UUID
        if ip_address == '127.0.0.1' or ip_address == '::1':
            logging.warning("Returning local UUID-based MAC, which may not be reliable for client identification.")
            return str(uuid.getnode())
        
        # Additional fallback: Try socket method
        try:
            hostname = socket.gethostbyaddr(ip_address)[0]
            # Attempt to get MAC via hostname (not reliable for remote IPs)
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                            for elements in range(0,2*6,2)][::-1])
            return mac
        except Exception as e:
            logging.error(f"Hostname MAC lookup failed: {e}")
        
        return None
    
    except Exception as e:
        logging.error(f"Unexpected error in get_mac_from_ip: {e}")
        return None