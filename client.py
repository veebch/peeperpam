import network
import usocket as socket
import ubinascii
import uasyncio as asyncio
import os

# Replace these with your Wi-Fi credentials
SSID = 'wifi SSID goes here'
PASSWORD = 'password goes here'

# Replace with your Raspberry Pi's IP address
SERVER_IP = 'IP Address here'
SERVER_PORT = 6789

# Connect to Wi-Fi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

while not wlan.isconnected():
    pass

print("Connected to Wi-Fi")
print("IP Address:", wlan.ifconfig()[0])

class WebSocketClient:
    def __init__(self, server_ip, port):
        self.server_ip = server_ip
        self.port = port
        self.sock = None

    def connect(self):
        addr_info = socket.getaddrinfo(self.server_ip, self.port)
        addr = addr_info[0][-1]
        self.sock = socket.socket()
        self.sock.connect(addr)
        print(f"Connected to {self.server_ip}:{self.port}")

        # Handshake
        sec_websocket_key = ubinascii.b2a_base64(os.urandom(16)).strip()
        handshake = (b"GET / HTTP/1.1\r\n"
                     b"Host: %s:%d\r\n"
                     b"Upgrade: websocket\r\n"
                     b"Connection: Upgrade\r\n"
                     b"Sec-WebSocket-Key: %s\r\n"
                     b"Sec-WebSocket-Version: 13\r\n\r\n") % (self.server_ip.encode(), self.port, sec_websocket_key)
        self.sock.send(handshake)
        response = self.sock.recv(1024)
        print("Handshake response:", response)
        if b"101" not in response:
            raise ValueError("Handshake failed")
        print("Handshake successful")

    def read_bytes(self, num_bytes):
        data = bytearray()
        while len(data) < num_bytes:
            packet = self.sock.recv(num_bytes - len(data))
            if not packet:
                raise ValueError("Connection closed before receiving all data")
            data.extend(packet)
        return data

    def recv(self):
        first_byte, second_byte = self.read_bytes(2)
        fin = first_byte & 0b10000000
        opcode = first_byte & 0b00001111
        masked = second_byte & 0b10000000
        payload_length = second_byte & 0b01111111

        if payload_length == 126:
            payload_length = int.from_bytes(self.read_bytes(2), 'big')
        elif payload_length == 127:
            payload_length = int.from_bytes(self.read_bytes(8), 'big')

        if masked:
            masking_key = self.read_bytes(4)
            payload = bytearray(self.read_bytes(payload_length))
            for i in range(payload_length):
                payload[i] ^= masking_key[i % 4]
        else:
            payload = self.read_bytes(payload_length)

        if opcode == 0x8:  # Close frame
            print("Received close frame")
            self.send_close_frame()
            return None

        if opcode == 0x9:  # Ping frame
            print("Received ping frame")
            self.send_pong_frame()
            return None

        message = payload.decode('utf-8')
        print("Received message:", message)
        return message

    def send_frame(self, opcode, payload=b''):
        frame = bytearray()
        frame.append(0x80 | opcode)
        payload_length = len(payload)

        if payload_length < 126:
            frame.append(0x80 | payload_length)
        elif payload_length <= 0xFFFF:
            frame.append(0x80 | 126)
            frame.extend(payload_length.to_bytes(2, 'big'))
        else:
            frame.append(0x80 | 127)
            frame.extend(payload_length.to_bytes(8, 'big'))

        masking_key = os.urandom(4)
        frame.extend(masking_key)

        if payload:
            masked_payload = bytearray(payload)
            for i in range(len(masked_payload)):
                masked_payload[i] ^= masking_key[i % 4]
            frame.extend(masked_payload)

        self.sock.send(frame)

    def send_close_frame(self):
        self.send_frame(0x8)
        print("Close frame sent")

    def send_pong_frame(self):
        self.send_frame(0xA)
        print("Pong frame sent")

    def close(self):
        if self.sock:
            self.send_close_frame()
            self.sock.close()
            self.sock = None
        print("Socket closed")

async def listen_for_signal():
    while True:
        ws = WebSocketClient(SERVER_IP, SERVER_PORT)
        try:
            ws.connect()
            while True:
                signal = ws.recv()
                if signal and "Signal" in signal:
                    print("Signal received")
                    perform_action()
        except Exception as e:
            print("Error:", e)
        finally:
            ws.close()
            await asyncio.sleep(5)  # Reconnect after a delay if the connection is lost

def perform_action():
    print("Performing the action!")


asyncio.run(listen_for_signal())


