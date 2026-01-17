#!/usr/bin/env python3
import asyncio
import websockets
import subprocess
import re
import signal
import sys
import json
import time
import logging
import argparse
from collections import defaultdict
from datetime import datetime

class CameraMonitor:
    def __init__(self, show_preview=False):
        self.current_detection = {"person": 0, "cup": 0}
        self.all_objects = {}
        self.signal_active = False
        self.connected_clients = set()
        self.camera_process = None
        self.frame_count = 0
        self.last_detection_time = None
        self.show_preview = show_preview
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        
    async def start_camera_monitoring(self):
        """Start the camera process and monitor its output"""
        # Build command based on preview preference
        cmd = ["rpicam-vid", "-v", "2", "-t", "0", "--inline"]
        
        if not self.show_preview:
            cmd.append("-n")  # No preview for headless/SSH mode
            
        cmd.extend([
            "--post-process-file", "/home/pi/rpicam-apps/assets/hailo_yolo8_inference.json",
            "--width", "640", "--height", "640",
            "--framerate", "10", "-o", "-"
        ])
        
        mode = "with preview window" if self.show_preview else "headless (no preview)"
        self.logger.info(f"Starting camera monitoring {mode}...")
        self.logger.info(f"Command: {' '.join(cmd)}")
        
        if self.show_preview:
            self.logger.info("📺 Preview window should appear for testing")
        else:
            self.logger.info("🔒 Running headless - suitable for SSH connections")
        
        try:
            self.camera_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            
            self.logger.info("Camera process started successfully")
            await self.process_camera_output()
            
        except Exception as e:
            self.logger.error(f"Error starting camera: {e}")
    
    async def process_camera_output(self):
        """Process camera output and detect objects"""
        if not self.camera_process:
            return
            
        self.logger.info("Starting camera output processing...")
        
        async for line_bytes in self.camera_process.stdout:
            try:
                line = line_bytes.decode('utf-8').strip()
                
                # Log all output for debugging (you can reduce this later)
                if line and not line.startswith('#'):
                    self.logger.debug(f"Camera output: {line}")
                
                # Parse YOLO detection output
                if self.is_detection_line(line):
                    self.frame_count += 1
                    self.last_detection_time = datetime.now()
                    
                    self.logger.info(f"Frame {self.frame_count}: Processing detection line")
                    self.parse_detection_line(line)
                    await self.update_signal_status()
                    
            except UnicodeDecodeError as e:
                self.logger.warning(f"Failed to decode line: {e}")
            except Exception as e:
                self.logger.error(f"Error processing camera output: {e}")
    
    def is_detection_line(self, line):
        """Check if this line contains object detection info"""
        detection_indicators = [
            "Object detected:",
            "Detection:",
            "Found:",
            "person",
            "cup",
            "bottle",
            "chair",
            "dining table"
        ]
        return any(indicator in line.lower() for indicator in detection_indicators)
    
    def parse_detection_line(self, line):
        """Parse a detection line and update object counts"""
        # Reset counts for this frame
        self.current_detection = {"person": 0, "cup": 0}
        self.all_objects = {}
        
        line_lower = line.lower()
        
        # Log the raw detection line
        self.logger.info(f"Raw detection: {line}")
        
        # Parse different object types and their counts
        objects_found = []
        
        # Count persons
        person_matches = len(re.findall(r'\bperson\b', line_lower))
        if person_matches > 0:
            self.current_detection["person"] = person_matches
            self.all_objects["person"] = person_matches
            objects_found.append(f"{person_matches} person(s)")
        
        # Count cups
        cup_matches = len(re.findall(r'\bcup\b', line_lower))
        if cup_matches > 0:
            self.current_detection["cup"] = cup_matches
            self.all_objects["cup"] = cup_matches
            objects_found.append(f"{cup_matches} cup(s)")
        
        # Count other common objects for verbose logging
        other_objects = ["bottle", "chair", "dining table", "laptop", "cell phone", "book"]
        for obj in other_objects:
            matches = len(re.findall(fr'\b{obj}\b', line_lower))
            if matches > 0:
                self.all_objects[obj] = matches
                objects_found.append(f"{matches} {obj}(s)")
        
        # Verbose logging
        if objects_found:
            self.logger.info(f"Frame {self.frame_count} objects: {', '.join(objects_found)}")
            self.logger.info(f"Target detection: {self.current_detection['person']} person(s), {self.current_detection['cup']} cup(s)")
        else:
            self.logger.debug(f"Frame {self.frame_count}: No relevant objects detected")
    
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
                self.logger.warning("🚨 SIGNAL ACTIVATED: 1 person + 1 cup detected!")
                self.logger.info(f"All objects in frame: {self.all_objects}")
                await self.broadcast_signal()
            else:
                self.logger.info("Signal deactivated")
        
        # Log periodic status for monitoring
        if self.frame_count % 30 == 0:  # Every 30 frames
            self.logger.info(f"Status update - Frame {self.frame_count}: Signal {'ACTIVE' if self.signal_active else 'inactive'}")
            if self.all_objects:
                self.logger.info(f"Current scene: {self.all_objects}")
    
    async def broadcast_signal(self):
        """Broadcast signal to all connected WebSocket clients"""
        if not self.connected_clients:
            self.logger.debug("No WebSocket clients connected for broadcast")
            return
            
        message = {
            "alert": True,
            "timestamp": datetime.now().isoformat(),
            "frame": self.frame_count,
            "target_detection": self.current_detection,
            "all_objects": self.all_objects,
            "message": "1 person and 1 cup detected"
        }
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for websocket in self.connected_clients:
            try:
                await websocket.send(message_str)
                self.logger.info(f"Alert sent to WebSocket client")
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(websocket)
        
        # Remove disconnected clients
        self.connected_clients -= disconnected
        if disconnected:
            self.logger.info(f"Removed {len(disconnected)} disconnected WebSocket clients")
    
    async def handle_websocket_connection(self, websocket, path):
        """Handle new WebSocket connections"""
        self.connected_clients.add(websocket)
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.logger.info(f"New WebSocket connection from {client_info}. Total clients: {len(self.connected_clients)}")
        
        try:
            # Send periodic updates while signal is active
            while True:
                if self.signal_active:
                    message = {
                        "status": "active",
                        "timestamp": datetime.now().isoformat(),
                        "frame": self.frame_count,
                        "detection": self.current_detection,
                        "all_objects": self.all_objects
                    }
                    await websocket.send(json.dumps(message))
                    await asyncio.sleep(0.2)  # Send every 0.2 seconds while active
                else:
                    # Send periodic ping to keep connection alive
                    try:
                        await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    except asyncio.TimeoutError:
                        await websocket.ping()
                        await asyncio.sleep(1.0)
                        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"WebSocket connection from {client_info} closed normally")
        except Exception as e:
            self.logger.error(f"WebSocket error with {client_info}: {e}")
        finally:
            self.connected_clients.discard(websocket)
            self.logger.info(f"Client {client_info} disconnected. Remaining clients: {len(self.connected_clients)}")
    
    async def start_websocket_server(self):
        """Start the WebSocket server"""
        self.logger.info("Starting WebSocket server on 0.0.0.0:6789")
        async with websockets.serve(self.handle_websocket_connection, "0.0.0.0", 6789):
            await asyncio.Future()  # Run forever
    
    async def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Starting cleanup process...")
        if self.camera_process and self.camera_process.returncode is None:
            self.logger.info("Terminating camera process...")
            self.camera_process.terminate()
            try:
                await asyncio.wait_for(self.camera_process.wait(), timeout=5.0)
                self.logger.info("Camera process terminated gracefully")
            except asyncio.TimeoutError:
                self.logger.warning("Camera process didn't terminate, killing...")
                self.camera_process.kill()
        self.logger.info("Cleanup complete")
    
    async def run(self):
        """Main run loop"""
        try:
            # Start both camera monitoring and WebSocket server concurrently
            await asyncio.gather(
                self.start_camera_monitoring(),
                self.start_websocket_server()
            )
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            await self.cleanup()

def signal_handler(signum, frame):
    logging.info(f"Received signal {signum}")
    sys.exit(0)

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Combined Camera Monitor with Object Detection')
    parser.add_argument('--preview', action='store_true', 
                       help='Show camera preview window (for local testing)')
    parser.add_argument('--headless', action='store_true',
                       help='Run without preview window (for SSH/remote)')
    
    args = parser.parse_args()
    
    # Determine preview mode
    show_preview = False
    if args.preview:
        show_preview = True
    elif args.headless:
        show_preview = False
    else:
        # Auto-detect: check if DISPLAY is set (local) or not (SSH)
        import os
        show_preview = 'DISPLAY' in os.environ and os.environ['DISPLAY']
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    monitor = CameraMonitor(show_preview=show_preview)
    await monitor.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Combined Camera Monitor with Object Detection')
    parser.add_argument('--preview', action='store_true', 
                       help='Show camera preview window (for local testing)')
    parser.add_argument('--headless', action='store_true',
                       help='Run without preview window (for SSH/remote)')
    
    args = parser.parse_args()
    
    print("🔍 Combined Camera Monitor with Enhanced Detection")
    print("📡 WebSocket server will be available on ws://0.0.0.0:6789")
    print()
    
    if args.preview:
        print("📺 Preview mode: Camera window will be displayed")
    elif args.headless:
        print("🔒 Headless mode: No camera window (SSH-friendly)")
    else:
        display_available = 'DISPLAY' in __import__('os').environ
        if display_available:
            print("📺 Auto-detected: Local display available, showing preview")
        else:
            print("🔒 Auto-detected: No display (SSH), running headless")
    
    print()
    print("Usage examples:")
    print("  python3 combined_monitor.py --preview    # Force preview window")
    print("  python3 combined_monitor.py --headless   # Force no preview") 
    print("  python3 combined_monitor.py             # Auto-detect")
    print()
    print("Press Ctrl+C to stop")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")