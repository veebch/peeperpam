#!/usr/bin/env python3
import asyncio
import websockets
import subprocess
import re
import signal
import sys
from collections import defaultdict

class CameraMonitor:
    def __init__(self):
        self.current_detection = {"person": 0, "cup": 0}
        self.signal_active = False
        self.connected_clients = set()
        self.camera_process = None
        
    async def start_camera_monitoring(self):
        """Start the camera process and monitor its output"""
        cmd = [
            "rpicam-hello", "-n", "-v", "2", "-t", "0",
            "--post-process-file", "/home/pi/rpicam-apps/assets/hailo_yolo8_inference.json",
            "--lores-width", "640", "--lores-height", "640"
        ]
        
        try:
            self.camera_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            
            print("Camera monitoring started")
            await self.process_camera_output()
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    async def process_camera_output(self):
        """Process camera output and detect objects"""
        if not self.camera_process:
            return
            
        async for line_bytes in self.camera_process.stdout:
            line = line_bytes.decode('utf-8').strip()
            
            # Parse YOLO detection output
            # Looking for lines like: "Object detected: person (confidence: 0.85)"
            if "Object" in line and ("person" in line or "cup" in line):
                self.parse_detection_line(line)
                await self.update_signal_status()
    
    def parse_detection_line(self, line):
        """Parse a detection line and update object counts"""
        # Reset counts for this frame
        self.current_detection = {"person": 0, "cup": 0}
        
        # Count person detections
        person_matches = re.findall(r'person', line.lower())
        self.current_detection["person"] = len(person_matches)
        
        # Count cup detections  
        cup_matches = re.findall(r'cup', line.lower())
        self.current_detection["cup"] = len(cup_matches)
        
        print(f"Detected: {self.current_detection['person']} person(s), {self.current_detection['cup']} cup(s)")
    
    async def update_signal_status(self):
        """Check if signal conditions are met and update status"""
        # Signal active when exactly 1 person AND exactly 1 cup detected
        new_signal_active = (
            self.current_detection["person"] == 1 and 
            self.current_detection["cup"] == 1
        )
        
        if new_signal_active != self.signal_active:
            self.signal_active = new_signal_active
            if self.signal_active:
                print("🚨 SIGNAL ACTIVATED: 1 person + 1 cup detected!")
                await self.broadcast_signal()
            else:
                print("Signal deactivated")
    
    async def broadcast_signal(self):
        """Broadcast signal to all connected WebSocket clients"""
        if not self.connected_clients:
            return
            
        message = f"ALERT: 1 person and 1 cup detected - {self.current_detection}"
        disconnected = set()
        
        for websocket in self.connected_clients:
            try:
                await websocket.send(message)
                print(f"Signal sent to client")
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(websocket)
        
        # Remove disconnected clients
        self.connected_clients -= disconnected
    
    async def handle_websocket_connection(self, websocket, path):
        """Handle new WebSocket connections"""
        self.connected_clients.add(websocket)
        print(f"New WebSocket connection. Total clients: {len(self.connected_clients)}")
        
        try:
            # Send periodic updates while signal is active
            while True:
                if self.signal_active:
                    message = f"ACTIVE: 1 person + 1 cup detected"
                    await websocket.send(message)
                    await asyncio.sleep(0.2)  # Send every 0.2 seconds while active
                else:
                    # Send periodic ping to keep connection alive
                    try:
                        await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    except asyncio.TimeoutError:
                        await websocket.ping()
                        await asyncio.sleep(1.0)
                        
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            self.connected_clients.discard(websocket)
            print(f"Client disconnected. Remaining clients: {len(self.connected_clients)}")
    
    async def start_websocket_server(self):
        """Start the WebSocket server"""
        print("Starting WebSocket server on 0.0.0.0:6789")
        async with websockets.serve(self.handle_websocket_connection, "0.0.0.0", 6789):
            await asyncio.Future()  # Run forever
    
    async def cleanup(self):
        """Cleanup resources"""
        print("Cleaning up...")
        if self.camera_process and self.camera_process.returncode is None:
            self.camera_process.terminate()
            try:
                await asyncio.wait_for(self.camera_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.camera_process.kill()
        print("Cleanup complete")
    
    async def run(self):
        """Main run loop"""
        try:
            # Start both camera monitoring and WebSocket server concurrently
            await asyncio.gather(
                self.start_camera_monitoring(),
                self.start_websocket_server()
            )
        except KeyboardInterrupt:
            print("Received interrupt signal")
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            await self.cleanup()

def signal_handler(signum, frame):
    print(f"Received signal {signum}")
    sys.exit(0)

async def main():
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    monitor = CameraMonitor()
    await monitor.run()

if __name__ == "__main__":
    print("Starting Combined Camera Monitor with 1 Person + 1 Cup Detection")
    print("WebSocket server will be available on ws://0.0.0.0:6789")
    print("Press Ctrl+C to stop")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")