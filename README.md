# Peeper Pam

This is the server code that lives on the pi5 and the client code that lives on the pico W.

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

Now plug in the device to power, it will autorun


