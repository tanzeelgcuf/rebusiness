import requests
import socket
import sys

def check_port(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def check_ip_and_block():
    proxies = {'http': 'socks5://127.0.0.1:9999', 'https': 'socks5://127.0.0.1:9999'}
    
    print("-" * 40)
    print("🔍 DIAGNOSTICS REPORT")
    print("-" * 40)
    
    # 1. Check Gateway Tunnel
    if check_port(9999):
        print("✅ Local Gateway Tunnel (Port 9999): CONNECTED")
    else:
        print("❌ Local Gateway Tunnel (Port 9999): NOT FOUND")
        print("   -> Is 'start_local_gateway.sh' running on your Mac?")
        return

    # 2. Check IP via Tunnel
    try:
        print("\nChecking External IP via Tunnel...")
        my_ip = requests.get('https://api.ipify.org', proxies=proxies, timeout=10).text
        print(f"✅ Your Tunnel IP: {my_ip}")
    except Exception as e:
        print(f"❌ Failed to get IP via tunnel: {e}")
        return

    # 3. Check ThomasNet Block
    try:
        print("\nChecking ThomasNet Access...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        resp = requests.get('https://www.thomasnet.com', proxies=proxies, headers=headers, timeout=15)
        
        print(f"📡 ThomasNet Status Code: {resp.status_code}")
        
        if "DataDome" in resp.text:
            print("❌ RESULT: BLOCKED (DataDome DETECTED)")
            print("   -> Your IP is flagged. You MUST change it (Hotspot/Router restart).")
        elif resp.status_code in [403, 429]:
             print("❌ RESULT: BLOCKED (HTTP 403/429)")
        else:
            print("✅ RESULT: LOOKS GOOD! (Page loaded)")
            
    except Exception as e:
        print(f"❌ Connection Error to ThomasNet: {e}")

if __name__ == "__main__":
    check_ip_and_block()
