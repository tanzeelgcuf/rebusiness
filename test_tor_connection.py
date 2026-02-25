#!/usr/bin/env python3
"""
Quick test to verify Tor proxy is working
"""
import requests

def test_tor_connection():
    """Test if Tor proxy is working"""
    print("Testing Tor connection...")
    
    # Test without proxy (your real IP)
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        real_ip = response.json()["ip"]
        print(f"✓ Your real IP: {real_ip}")
    except Exception as e:
        print(f"✗ Failed to get real IP: {e}")
        return False
    
    # Test with Tor proxy
    try:
        proxies = {
            "http": "socks5://127.0.0.1:9050",
            "https": "socks5://127.0.0.1:9050"
        }
        response = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
        tor_ip = response.json()["ip"]
        print(f"✓ Tor IP: {tor_ip}")
        
        if real_ip != tor_ip:
            print(f"\n✅ SUCCESS! Tor is working correctly!")
            print(f"   Your IP changed from {real_ip} to {tor_ip}")
            return True
        else:
            print(f"\n❌ WARNING: IPs are the same. Tor may not be working.")
            return False
            
    except Exception as e:
        print(f"✗ Failed to connect through Tor: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Tor is running: brew services start tor")
        print("2. Wait a few seconds for Tor to establish circuits")
        print("3. Install requests[socks]: pip install requests[socks]")
        return False

if __name__ == "__main__":
    test_tor_connection()
