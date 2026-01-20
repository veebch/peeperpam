![Sketch](/images/hildegard-composite.jpg)

[![YouTube Channel Views](https://img.shields.io/youtube/channel/views/UCz5BOU9J9pB_O0B8-rDjCWQ?style=flat&logo=youtube&logoColor=red&labelColor=white&color=ffed53)](https://www.youtube.com/channel/UCz5BOU9J9pB_O0B8-rDjCWQ) [![Instagram](https://img.shields.io/github/stars/veebch?style=flat&logo=github&logoColor=black&labelColor=white&color=ffed53)](https://www.instagram.com/v_e_e_b/)

# Peeper Pam

An overengineered reboot of the old ThinkGeek C.H.I.M.P. monitor mirror. 

AKA How to make a desktop device that provides alerts when objects are detected on a live-stream by a server performing computer vision analysis. 

It uses a Raspberry Pi 5 with a camera and Raspberry Pi AI HAT+ 2 as the server, and a Pico W as the client. The system detects all objects but provides priority-based responses: person+cup combinations trigger 100% alerts, person detection alone triggers 70% response, cup detection triggers 30% response, and other interesting objects trigger 10% response. Alerts are sent via WebSocket with RGB LED color changes, PWM-controlled analog needle movement showing detection confidence, and UFO sound alerts for detections above 50% threshold.

## Explainer Video

Here's an overview video of the build and a demo of it in action (it shows the initial red led only version):

[![YouTube](http://i.ytimg.com/vi/Vn3WaVIr5v0/hqdefault.jpg)](https://www.youtube.com/watch?v=Vn3WaVIr5v0)


## Project Structure

### Server Components
- **combined_monitor.py** - Complete Raspberry Pi camera monitoring system that captures video, performs object detection using AI kit, and broadcasts all detected objects with confidence scores via WebSocket

### Client Components  
- **main.py** - MicroPython WebSocket client for Pico W that receives detection data and provides priority-based responses:
  - Person + Cup: 100% PWM alert (red LED)
  - Person only: 70% PWM response 
  - Cup only: 30% PWM response
  - Other objects: 10% PWM response
  - LED color transitions from green (0%) to red (100%) based on detection priority

##  Materials
### Server 
- Raspberry Pi 5
- Raspberry Pi AI+ 2 Kit
- Camera module 

### Detector
- Analogue voltmeter (5V) 
- Pico W
- 220 Ohm resistor
- 1K Ohm resistor
- MOSFET (We used a Small Signal BS170)
- A 4 legged RGB LED
- Passive buzzer

## Assembly

### Server

Connect the M2 expansion board from the AI kit to the Pi 5, connect the 22 pin ribbon cable from the CAM/DISP 0 port on the Pi.

### Detector

- From the Pico, GPIO 27 is soldered to the 1K Ohm resistor which in turn is soldered to the gate (middle pin) of the MOSFET. 
- The VSYS connection on the Pico is connected the positive terminal of the voltmeter. 
- The Cathode (negative) leg of the LED is connected to a GND pin on the Pico in series with the 220 ohm resistor. The Red, Green and Blue legs are connected to GP18, GP19 and GP20 respectively
- The passive buzzer positive terminal is connected to GPIO 15, and the negative terminal to GND
- The Source leg of the MOSFET is connected to the Negative terminal on the voltmeter, the Drain leg of the MOSFET is then connected to a GND GPIO on the Pico W. Here's a photo of the back of the detector

![Detector](/images/detector.jpg)

## Installing

First, make sure you have the rpicam-apps files in your home directory
```
cd ~
git clone https://github.com/raspberrypi/rpicam-apps
```

Copy this repository to the Pi 5 using the commands 
```
git clone https://github.com/veebch/peeperpam.git
```
Then copy the file `main.py` to the pico using Ampy (or Thonny)

## Running

### Prerequisites
Make sure you have the rpicam-apps installed:
```bash
cd ~
git clone https://github.com/raspberrypi/rpicam-apps
```

### Start the Complete Monitoring System
Set up Python environment and run the integrated server:
```bash
python3 -m venv ~/.venv
source ~/.venv/bin/activate
cd ~/peeperpam
pip install websockets  # Install required WebSocket library
python3 combined_monitor.py
```

This single command starts both the camera monitoring and WebSocket server that broadcasts all detected objects.

### Configure and Deploy the Client
1. **Edit configuration in `config.py`**:
   - WiFi credentials: Replace `SSID` and `PASSWORD` with your network details
   - Object detection: Customize `INTERESTING_OBJECTS` list to monitor different objects (from the [COCO 80](https://blog.roboflow.com/microsoft-coco-classes/) list by default but you can train on other image data)
   - Detection priorities: Adjust `PERSON_SCALE`, `CUP_SCALE`, and `OTHER_SCALE` values
   - Sound settings: Modify `SOUND_THRESHOLD`, `SOUND_COOLDOWN`, and UFO sound parameters
   - Hardware pins: Change pin assignments if using different GPIO connections

2. Copy both `main.py` and `config.py` to your Pico W using Ampy, Thonny, or your preferred method

3. Power on the Pico W - it will automatically connect to WiFi and start receiving detection alerts

### System Operation
- The system detects all objects but responds with different priority levels
- RGB LED changes from green (low priority) to red (high priority) 
- Analog needle shows detection confidence scaled by priority level
- UFO sound alert plays when detection confidence exceeds 50% threshold
- Sound includes 5-second cooldown to prevent constant triggering
- WebSocket connection automatically reconnects if interrupted

## Caveats

The MOSFET may be overkill for the LED and Voltmeter, but if you plan to use something that draws more current than an LED, then using SYSBUS means the 'alarm' peripheral can draw a lot more current than just a GPIO pin set to high (~16mA). 
