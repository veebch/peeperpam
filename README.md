# Peeper Pam
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

## Start the server running on the Pi 5
You do that on a virtual environment which you activate with
```
python3 -m venv ~/.venv
source ~/.venv/bin/activate
python3 server.py
```
Start the camera monitor script
```
./camera_monitor.sh
```

Now plug in the device to power, any time the camera registers a person the Red Led will light up and the needle/light level will give an approximation of the probability (1 == certainty)


