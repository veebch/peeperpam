import network
import usocket as socket
import ubinascii
import uasyncio as asyncio
import os
import time
import re
import ujson as json
from machine import Pin, PWM

# Replace these with your Wi-Fi credentials
SSID = <YOUR WIFI SSID>
PASSWORD = <YOUR WIFI PASSWORD>
# Replace with your Raspberry Pi's IP address
SERVER_IP = <IP ADDRESS OF RASPBERRY PI>
SERVER_PORT = 6789

# RGB LED pins with PWM
red_pin = PWM(Pin(18))
green_pin = PWM(Pin(19))
blue_pin = PWM(Pin(20))

# Set PWM frequency for LED
for pin in [red_pin, green_pin, blue_pin]:
    pin.freq(1000)
    pin.duty_u16(0)

# Alert PWM pin
alert = PWM(Pin(27))
alert.freq(1000)

# Connect to Wi-Fi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)
while not wlan.isconnected():
    pass
print("Connected to Wi-Fi")
print("IP Address:", wlan.ifconfig()[0])

def set_rgb_pwm(r, g, b):
    """Set RGB LED color using PWM values (0-65535)"""
    red_pin.duty_u16(r)
    green_pin.duty_u16(g)
    blue_pin.duty_u16(b)

def update_led_from_pwm(duty_ratio):
    """Update LED color based on PWM duty cycle (0.0 to 1.0)
    Green at 0%, transitions to red at 100%"""
    red = int(duty_ratio * 65535)
    green = int((1 - duty_ratio) * 65535)
    set_rgb_pwm(red, green, 0)

def set_duty_cycle(duty):
    # Clamp duty to 0.0-1.0 range
    duty = max(0.0, min(1.0, duty))
    alert.duty_u16(int(duty * 65535))
    # Update LED color to match PWM value
    update_led_from_pwm(duty)

def startup_sequence():
    """Startup sequence: ramp up to full over 2 seconds, then down over 2 seconds"""
    ramp_duration = 2.0
    steps = 100
    step_duration = ramp_duration / steps

    # Ramp up
    print("Starting up - ramping up...")
    for i in range(steps + 1):
        duty = i / steps
        set_duty_cycle(duty)
        time.sleep(step_duration)

    # Ramp down
    print("Ramping down...")
    for i in range(steps, -1, -1):
        duty = i / steps
        set_duty_cycle(duty)
        time.sleep(step_duration)

    print("Startup complete")

class WebSocketClient:
    def __init__(self, server_ip, port):
        self.server_ip = server_ip
        self.port = port
        self.sock = None

    def connect(self):
        while True:
            try:
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
                break
            except (OSError, ValueError) as e:
                print("Connection error:", e)
                if self.sock:
                    self.sock.close()
                self.sock = None
                print("Retrying connection in 5 seconds...")
                time.sleep(5)

    def read_bytes(self, num_bytes):
        data = bytearray()
        while len(data) < num_bytes:
            packet = self.sock.recv(num_bytes - len(data))
            if not packet:
                raise ValueError("Connection closed before receiving all data")
            data.extend(packet)
        return data

    def recv(self):
        try:
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
        except OSError as e:
            print("Recv error:", e)
            self.close()
            return None

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
            try:
                self.send_close_frame()
            except Exception as e:
                print("Error during close frame:", e)
            self.sock.close()
            self.sock = None
        print("Socket closed")

def parse_detection_data(message):
    """Parse modern JSON detection data from camera monitor"""
    try:
        data = json.loads(message)
        
        # Check if this is an alert with target detection
        if data.get("alert", False):
            # Get average confidence for PWM control
            avg_confidence = data.get("average_confidence", 0.0)
            
            # Log detailed detection info
            target_detection = data.get("target_detection", {})
            all_objects = data.get("all_objects", {})
            
            print(f"Alert! Target: {target_detection}")
            print(f"All objects: {all_objects}")
            print(f"Average confidence: {avg_confidence}")
            
            return avg_confidence
            
        elif data.get("status") == "active":
            # Ongoing detection - get current confidence
            avg_confidence = data.get("average_confidence", 0.0)
            print(f"Active detection - confidence: {avg_confidence}")
            return avg_confidence
            
    except (ValueError, KeyError) as e:
        print(f"Error parsing JSON: {e}")
        
        # Fallback to old string parsing for compatibility
        return parse_string_legacy(message)
    
    return 0.0

def parse_string_legacy(input_string):
    """Legacy string parsing for backward compatibility"""
    # Check if the string contains the word 'person'
    if 'person' in input_string:
        # Use regex to find the number in parentheses
        match = re.search(r'\(([\d.]+)\)', input_string)
        if match:
            number_in_parentheses = float(match.group(1))
        else:
            number_in_parentheses = 0
    else:
        number_in_parentheses = 0

    return number_in_parentheses

def perform_action(signal):
    print("Performing the action!")
    # Parse the detection data (JSON or legacy string)
    duty = parse_detection_data(signal)
    print(f"Setting PWM duty to: {duty}")
    set_duty_cycle(duty)

async def listen_for_signal():
    while True:
        ws = WebSocketClient(SERVER_IP, SERVER_PORT)
        try:
            ws.connect()
            while True:
                signal = ws.recv()
                if signal:
                    # Handle both JSON alerts and legacy string format
                    if signal.startswith('{') or "alert" in signal:
                        print("Detection signal received:", signal[:100] + "..." if len(signal) > 100 else signal)
                        perform_action(signal)
                    elif "Object" in signal:
                        print("Legacy signal received:", signal)
                        perform_action(signal)
        except Exception as e:
            print("Error:", e)
        finally:
            ws.close()
            await asyncio.sleep(5)

# Run startup sequence
startup_sequence()

asyncio.run(listen_for_signal())

