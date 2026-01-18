# PeeperPam Configuration File
# Edit these values to customize detection behavior and network settings

# ====== NETWORK SETTINGS ======
# WiFi credentials
SSID = "whyayefi"  # Replace with your actual WiFi SSID  
PASSWORD = "your_actual_password"  # Replace with your actual WiFi password

# Server connection
SERVER_IP = "peeper.local"  # Use hostname or IP address of your Raspberry Pi
SERVER_PORT = 6789

# ====== DETECTION PRIORITIES ======
# Object priority scaling factors (0.0 = no response, 1.0 = full response)
PERSON_SCALE = 0.7      # Person detection alone gets 70% response
CUP_SCALE = 0.3         # Cup detection alone gets 30% response  
OTHER_SCALE = 0.1       # Other interesting objects get 10% response

# High priority objects (will trigger person/cup scaled response)
PRIMARY_OBJECTS = ["person", "cup"]

# Interesting objects that trigger low-level responses
INTERESTING_OBJECTS = [
    "bottle", 
    "laptop", 
    "cell phone", 
    "book", 
    "tv",
    "mouse",
    "keyboard",
    "remote",
    "wine glass",
    "banana",
    "apple",
    "sandwich"
]

# ====== SOUND SETTINGS ======
# Sound trigger threshold (0.0 to 1.0)
SOUND_THRESHOLD = 0.5   # Trigger sound when detection confidence > 50%

# Sound timing
SOUND_COOLDOWN = 5.0    # Minimum seconds between sound triggers

# UFO sound parameters
UFO_BASE_FREQ = 600         # Base frequency (Hz)
UFO_FREQ_DEPTH = 300        # Pitch modulation depth
UFO_LFO_RATE = 15 / 2.3     # Pitch LFO frequency (Hz)
UFO_VOLUME_DEPTH = 0.3      # Amplitude modulation depth (0.0 - 1)
UFO_VOLUME = 1.0            # Global volume scale (0.0 - 1.0)

# Sound timing phases
UFO_FADE_IN_SEC = 0.1
UFO_SUSTAIN_SEC = 2.0
UFO_FADE_OUT_SEC = 1.0
UFO_STEP_MS = 5             # CPU delay between updates

# ====== CONNECTION SETTINGS ======
# WiFi connection parameters
WIFI_MAX_ATTEMPTS = 100     # Maximum connection attempts (10 seconds total)
WIFI_RETRY_DELAY = 0.1      # Seconds between connection attempts

# Network stabilization
NETWORK_STABILIZE_DELAY = 3  # Seconds to wait after WiFi connection

# WebSocket reconnection
WEBSOCKET_RETRY_DELAY = 5   # Seconds to wait before reconnecting on error