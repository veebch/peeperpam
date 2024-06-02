[![YouTube Channel Views](https://img.shields.io/youtube/channel/views/UCz5BOU9J9pB_O0B8-rDjCWQ?style=flat&logo=youtube&logoColor=red&labelColor=white&color=ffed53)](https://www.youtube.com/channel/UCz5BOU9J9pB_O0B8-rDjCWQ) [![Instagram](https://img.shields.io/github/stars/veebch?style=flat&logo=github&logoColor=black&labelColor=white&color=ffed53)](https://www.instagram.com/v_e_e_b/)

# Peeper Pam

How to make a desktop device that receives alerts from a server that is performing computer vision analysis on a live stream. It uses a Raspberry pi 5, with a camera and AI kit as the server, and a Pico W as the client.

##  Materials
### Server 
- Raspberry Pi 5
- Kit
- camera module 

### Detector
- Analogue voltmeter (5V)
- Pico
- 220 ohm resistor
- 1K ohm resistor
- Mosfet
- Red LED

## Assembly

## Installing

## Running

### Start the server running on the Pi 5
You do that on a virtual environment which you activate with
```
python3 -m venv ~/.venv
source ~/.venv/bin/activate
python3 server.py
```
### Start the camera monitor script
```
./camera_monitor.sh
```

Now plug in the device to power, any time the camera registers a person the Red Led will light up and the needle/light level will give an approximation of the probability (1 == certainty)


