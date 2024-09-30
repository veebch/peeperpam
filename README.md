![Sketch](/images/actionshot.png)

[![YouTube Channel Views](https://img.shields.io/youtube/channel/views/UCz5BOU9J9pB_O0B8-rDjCWQ?style=flat&logo=youtube&logoColor=red&labelColor=white&color=ffed53)](https://www.youtube.com/channel/UCz5BOU9J9pB_O0B8-rDjCWQ) [![Instagram](https://img.shields.io/github/stars/veebch?style=flat&logo=github&logoColor=black&labelColor=white&color=ffed53)](https://www.instagram.com/v_e_e_b/)

# Peeper Pam

An overengineered reboot of the old ThinkGeek C.H.I.M.P. monitor mirror. 

AKA How to make a desktop device that provides alerts you when human(s) are detected on a live-stream by a server that is performing computer vision analysis. 

It uses a Raspberry Pi 5, with a camera and a Raspberry Pi AI kit as the server, and a Pico W as the client. Alerts are sent to the Pico using websockets and alerts are made by lighting an LED and showing model confidence for detection of 'person' using an analogue needle that registers on a scale of 0-1.

## Explainer Video

Here's an overview video of the build and a demo of it in action:

[![YouTube](http://i.ytimg.com/vi/Vn3WaVIr5v0/hqdefault.jpg)](https://www.youtube.com/watch?v=Vn3WaVIr5v0)


##  Materials
### Server 
- Raspberry Pi 5
- Raspberry Pi AI Kit
- Camera module 

### Detector
- Analogue voltmeter (5V) 
- Pico W
- 220 Ohm resistor
- 1K Ohm resistor
- MOSFET (We used a Small Signal BS170)
- Red LED

## Assembly

### Server

Connect the M2 expansion board from the AI kit to the Pi 5, connect the 22 pin ribbon cable from the CAM/DISP 0 port on the Pi.

### Detector

- From the Pico GPIO 28 is soldered to the 1K Ohm resistor which in turn is soldered to the gate of the MOSFET. 
- The SYSBUS connection is connected the positive terminal of the voltmeter. 
- The positive terminal on the voltmeter is then connected to one end the 220 Ohm resistor and the other end of the resistor to the Anode (positive) leg of the LED. 
- The Cathode (negative) leg of the LED is then connected to the Source leg on the MOSFET. 
- The Source leg of the MOSFET is connected to the Negative terminal on the voltmeter, the Drain leg of the MOSFET is then connected to a GND GPIO on the Pico W. Here's a photo of the back of the detector

![Detector](/images/detector.jpg)

## Installing

Copy this repository to the Pi 5 using the commands 
```
cd ~
git clone https://github.com/veebch/peeperpam.git
```
Then copy the file `main.py` to the pico using Ampy (or Thonny)

## Running

### Start the server running on the Pi 5
You do that on a virtual environment which you activate with
```
python3 -m venv ~/.venv
source ~/.venv/bin/activate
cd ~/peeperpam
python3 server.py
```
### Start the camera monitor script
```
./camera_monitor.sh
```

Now plug in the device to power, any time the camera registers a person the Red Led will light up and the needle/light level will give an approximation of the probability (1 == certainty)

## Caveats

The MOSFET may be overkill for the LED and Voltmeter, but if you plan to use something that draws more current than an LED, then using SYSBUS means the 'alarm' peripheral can draw a lot more current than just a GPIO pin set to high (~16mA). 
