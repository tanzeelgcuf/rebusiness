import socket
import threading
import select
import sys
import struct

"""
Simple SOCKS5 Server for Local Tunneling
"""

class SocksProxy:
    def __init__(self, host='127.0.0.1', port=1080):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):
        try:
            self.server.bind((self.host, self.port))
            self.server.listen(20)
            print(f"✅ SOCKS5 Proxy listening on {self.host}:{self.port}")
        except Exception as e:
            print(f"❌ Failed to bind to {self.host}:{self.port}: {e}")
            return

        while True:
            try:
                client, addr = self.server.accept()
                t = threading.Thread(target=self.handle_client, args=(client,))
                t.daemon = True
                t.start()
            except KeyboardInterrupt:
                break
            except Exception:
                pass

    def handle_client(self, client):
        remote = None
        try:
            # 1. Negotiation
            # Client sends: VER NMETHODS METHODS
            ver = client.recv(1)
            if not ver: return
            nmethods = client.recv(1)
            methods = client.recv(nmethods[0]) # Py3 byte index is int
            
            # Server responds: VER METHOD (00 = No Auth)
            client.sendall(b'\x05\x00')
            
            # 2. Request
            # Client sends: VER CMD RSV ATYP DST.ADDR DST.PORT
            ver = client.recv(1)
            cmd = client.recv(1)
            rsv = client.recv(1)
            atyp = client.recv(1)
            
            if cmd != b'\x01': # CONNECT
                # Only support CONNECT
                client.close()
                return
            
            dest_addr = ""
            
            if atyp == b'\x01': # IPv4
                addr = client.recv(4)
                dest_addr = socket.inet_ntoa(addr)
            elif atyp == b'\x03': # Domain
                addr_len = client.recv(1)[0]
                dest_addr = client.recv(addr_len).decode()
            elif atyp == b'\x04': # IPv6
                client.close()
                return

            port_bytes = client.recv(2)
            dest_port = struct.unpack('>H', port_bytes)[0]
            
            # Connect to remote
            remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # remote.settimeout(10)
            remote.connect((dest_addr, dest_port))
            
            # Reply Success
            bind_addr = socket.inet_aton('0.0.0.0')
            bind_port = struct.pack('>H', 0)
            reply = b'\x05\x00\x00\x01' + bind_addr + bind_port
            client.sendall(reply)
            
            # 3. Exchange
            self.exchange_loop(client, remote)
            
        except Exception as e:
            # print(f"Proxy error: {e}")
            pass
        finally:
            try: client.close()
            except: pass
            if remote:
                try: remote.close()
                except: pass

    def exchange_loop(self, client, remote):
        try:
            while True:
                r, w, x = select.select([client, remote], [], [], 60)
                if not r: break # Timeout
                
                if client in r:
                    data = client.recv(8192)
                    if not data: break
                    remote.sendall(data)
                
                if remote in r:
                    data = remote.recv(8192)
                    if not data: break
                    client.sendall(data)
        except:
            pass

if __name__ == '__main__':
    port = 1080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    SocksProxy(port=port).run()
