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
SSID = "whyayefi"  # Replace with your actual WiFi SSID  
PASSWORD = "your_actual_password"  # Replace with your actual WiFi password
# Replace with your Raspberry Pi's IP address
SERVER_IP = "peeper.local"  # Use hostname instead of IP
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
print("Connecting to WiFi network:", SSID)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
print("WiFi interface activated")

# Force fresh connection - disconnect first if connected
if wlan.isconnected():
    print("Forcing WiFi disconnect to ensure fresh connection...")
    wlan.disconnect()
    time.sleep(2)  # Wait for disconnect
    print("WiFi disconnected")

print("Attempting to connect...")
wlan.connect(SSID, PASSWORD)
print("Connection request sent, waiting for connection...")

connection_attempts = 0
max_attempts = 100  # 10 seconds total
while not wlan.isconnected() and connection_attempts < max_attempts:
    connection_attempts += 1
    if connection_attempts % 10 == 0:  # Log every 1 second
        print("Still connecting... (attempt", connection_attempts, ")")
    time.sleep(0.1)

if not wlan.isconnected():
    print("Failed to connect to WiFi after", max_attempts/10, "seconds")
    print("WiFi Status:", wlan.status())
    print("Check your SSID and password")
    # Don't continue without WiFi
    while True:
        time.sleep(1)

print("Connected to Wi-Fi successfully")
ip_info = wlan.ifconfig()
print("IP Address:", ip_info[0])
print("Subnet Mask:", ip_info[1])
print("Gateway:", ip_info[2])
print("DNS:", ip_info[3])

# Wait a moment for network stack to fully initialize
print("Waiting for network stack to stabilize...")
time.sleep(3)

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

def set_duty_cycle(duty, verbose=True):
    # Clamp duty to 0.0-1.0 range
    original_duty = duty
    duty = max(0.0, min(1.0, duty))
    if original_duty != duty and verbose:
        print("WARNING: Duty cycle clamped from", original_duty, "to", duty)
    
    pwm_value = int(duty * 65535)
    alert.duty_u16(pwm_value)
    if verbose:
        print("PWM set to", duty, "(", pwm_value, "/65535)")
    
    # Update LED color to match PWM value
    update_led_from_pwm(duty)
    if verbose:
        red_val = int(duty*65535)
        green_val = int((1-duty)*65535)
        print("LED color updated (red:", red_val, ", green:", green_val, ")")

def startup_sequence():
    """Startup sequence: ramp up to full over 2 seconds, then down over 2 seconds"""
    ramp_duration = 2.0
    steps = 100
    step_duration = ramp_duration / steps

    # Ramp up (reduce logging)
    print("Starting up - ramping up...")
    for i in range(steps + 1):
        duty = i / steps
        set_duty_cycle(duty, verbose=False)  # Suppress verbose output during startup
        time.sleep(step_duration)

    # Ramp down
    print("Ramping down...")
    for i in range(steps, -1, -1):
        duty = i / steps
        set_duty_cycle(duty, verbose=False)  # Suppress verbose output during startup
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
                print("Resolving server address...")
                addr_info = socket.getaddrinfo(self.server_ip, self.port, socket.AF_INET)  # Force IPv4
                addr = addr_info[0][-1]
                print("Server address resolved to:", addr)
                
                print("Creating socket...")
                self.sock = socket.socket()
                print("Connecting to server...")
                self.sock.connect(addr)
                print("Connected to", self.server_ip, ":", self.port)

                # Handshake - use original working format
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
                print("Error type:", type(e).__name__)
                if hasattr(e, 'errno'):
                    print("Error number:", e.errno)
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
    """Parse detection data and return appropriate PWM duty cycle"""
    print("Parsing detection data...")
    try:
        data = json.loads(message)
        print("Successfully parsed JSON data")
        
        all_objects = data.get("all_objects", {})
        avg_confidence = data.get("average_confidence", 0.0)
        is_alert = data.get("alert", False)
        
        if all_objects:
            print("All objects detected:", all_objects)
            
            # Priority 1: High alert for person+cup combination
            if is_alert:
                print("HIGH PRIORITY ALERT!")
                conf_percent = avg_confidence * 100
                print("Alert confidence:", avg_confidence, "(", conf_percent, "%)")
                return avg_confidence
            
            # Priority 2: Respond to person detection (medium priority)
            elif "person" in all_objects:
                person_data = all_objects["person"]
                if isinstance(person_data, dict):
                    person_conf = person_data["confidence"]
                    print("Person detected - confidence:", person_conf)
                    # Scale down to 70% for person-only detection
                    return person_conf * 0.7
                    
            # Priority 3: Respond to cup detection (lower priority)
            elif "cup" in all_objects:
                cup_data = all_objects["cup"]
                if isinstance(cup_data, dict):
                    cup_conf = cup_data["confidence"]
                    print("Cup detected - confidence:", cup_conf)
                    # Scale down to 30% for cup-only detection
                    return cup_conf * 0.3
                    
            # Priority 4: Other interesting objects (very low response)
            else:
                interesting_objects = ["bottle", "laptop", "cell phone", "book", "tv"]
                for obj in interesting_objects:
                    if obj in all_objects:
                        obj_data = all_objects[obj]
                        if isinstance(obj_data, dict):
                            obj_conf = obj_data["confidence"]
                                print(obj + " detected - confidence:", obj_conf)
        print("Error parsing JSON:", str(e))
        
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
    print("Processing detection signal!")
    # Parse the detection data (JSON or legacy string)
    duty = parse_detection_data(signal)
    if duty > 0:
        print("Setting PWM duty to:", duty)
        set_duty_cycle(duty)
    else:
        print("No significant detection - PWM remains at current level")

async def listen_for_signal():
    while True:
        ws = WebSocketClient(SERVER_IP, SERVER_PORT)
        try:
            ws.connect()
            while True:
                signal = ws.recv()
                if signal:
                    # Handle all JSON detection messages
                    if signal.startswith('{'):
                        print("Detection message received")
                        perform_action(signal)
                    elif "Object" in signal or "person" in signal:
                        print("Legacy signal received:", signal)
                        perform_action(signal)
                    else:
                        print("Server message:", signal)
        except Exception as e:
            print("Error:", e)
        finally:
            ws.close()
            await asyncio.sleep(5)

# Run startup sequence
startup_sequence()

asyncio.run(listen_for_signal())

