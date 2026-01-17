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
        self.current_confidence = {"person": 0.0, "cup": 0.0}
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
        # Use different commands for preview vs headless mode
        if self.show_preview:
            # Use rpicam-hello for preview mode - it's designed for this
            cmd = [
                "rpicam-hello", "-v", "2", "-t", "0",
                "--post-process-file", "/home/pi/rpicam-apps/assets/hailo_yolov8_inference.json",
                "--lores-width", "640", "--lores-height", "640"
            ]
        else:
            # Use rpicam-vid for headless mode with output capture
            cmd = [
                "rpicam-vid", "-n", "-v", "2", "-t", "0", "--inline",
                "--post-process-file", "/home/pi/rpicam-apps/assets/hailo_yolov8_inference.json",
                "--width", "640", "--height", "640",
                "--framerate", "10", "-o", "-"
            ]

        mode = "with preview window (rpicam-hello)" if self.show_preview else "headless (rpicam-vid)"
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
        """Parse a detection line and update object counts with confidence"""
        # Reset for this frame
        self.current_detection = {"person": 0, "cup": 0}
        self.current_confidence = {"person": 0.0, "cup": 0.0}
        self.all_objects = {}

        line_lower = line.lower()

        # Log the raw detection line
        self.logger.info(f"Raw detection: {line}")

        # Parse different object types and their counts with confidence
        objects_found = []
        
        # Define all objects we want to detect with confidence
        target_objects = ["person", "cup", "bottle", "chair", "dining table", "laptop", "cell phone", "book", "mouse", "keyboard", "tv", "car", "bicycle", "dog", "cat"]
        
        for obj in target_objects:
            # Pattern to match: object_name[optional_stuff] (confidence_score)
            pattern = fr'{obj}[^(]*\(([\d.]+)\)'
            matches = re.findall(pattern, line_lower)
            if matches:
                confidences = [float(conf) for conf in matches]
                avg_conf = sum(confidences) / len(confidences)
                self.all_objects[obj] = {"count": len(matches), "confidence": avg_conf}
                objects_found.append(f"{len(matches)} {obj}(s) @{avg_conf:.2f}")
                
                # Update legacy fields for backwards compatibility
                if obj == "person":
                    self.current_detection["person"] = len(matches)
                    self.current_confidence["person"] = avg_conf
                elif obj == "cup":
                    self.current_detection["cup"] = len(matches)
                    self.current_confidence["cup"] = avg_conf

        # Verbose logging
        if objects_found:
            self.logger.info(f"Frame {self.frame_count} objects: {', '.join(objects_found)}")
        else:
            self.logger.debug(f"Frame {self.frame_count}: No objects detected")

    async def update_signal_status(self):
        """Broadcast detection status for any detected objects"""
        # Always broadcast if we have any objects detected
        has_objects = bool(self.all_objects)
        
        # Special case: high priority alert for person+cup combination
        person_cup_alert = (
            self.current_detection["person"] == 1 and
            self.current_detection["cup"] == 1
        )
        
        if has_objects:
            await self.broadcast_signal(alert=person_cup_alert)
            if person_cup_alert:
                self.logger.warning("🚨 HIGH PRIORITY: 1 person + 1 cup detected!")

        # Update signal status for legacy compatibility
        self.signal_active = person_cup_alert

        # Log periodic status for monitoring
        if self.frame_count % 30 == 0:  # Every 30 frames
            status = "HIGH PRIORITY" if person_cup_alert else ("DETECTING" if has_objects else "idle")
            self.logger.info(f"Status update - Frame {self.frame_count}: {status}")
            if self.all_objects:
                self.logger.info(f"Current scene: {self.all_objects}")

    async def broadcast_signal(self, alert=False):
        """Broadcast detection data to all connected WebSocket clients"""
        if not self.connected_clients:
            self.logger.debug("No WebSocket clients connected for broadcast")
            return

        # Calculate overall average confidence from all detected objects
        if self.all_objects:
            total_confidence = sum(obj["confidence"] for obj in self.all_objects.values() if isinstance(obj, dict))
            avg_confidence = total_confidence / len([obj for obj in self.all_objects.values() if isinstance(obj, dict)])
        else:
            avg_confidence = 0.0

        # Create detection summary
        object_summary = []
        for obj_name, obj_data in self.all_objects.items():
            if isinstance(obj_data, dict):
                object_summary.append(f"{obj_data['count']} {obj_name}(s) @{obj_data['confidence']:.2f}")
            else:
                object_summary.append(f"{obj_data} {obj_name}(s)")

        # Send modern JSON format with rich object detection data
        message = {
            "alert": alert,
            "timestamp": datetime.now().isoformat(),
            "frame": self.frame_count,
            "target_detection": self.current_detection,  # Legacy compatibility
            "target_confidence": self.current_confidence,  # Legacy compatibility
            "average_confidence": round(avg_confidence, 3),
            "all_objects": self.all_objects,
            "summary": ", ".join(object_summary),
            "message": f"Objects detected: {', '.join(object_summary)}" if object_summary else "No objects detected"
        }

        message_str = json.dumps(message)
        disconnected = set()

        for websocket in self.connected_clients:
            try:
                await websocket.send(message_str)
                log_level = "WARNING" if alert else "INFO"
                priority = "[ALERT] " if alert else ""
                self.logger.log(getattr(logging, log_level), f"{priority}Detection sent to WebSocket client: {message['summary']}")
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(websocket)

        # Remove disconnected clients
        self.connected_clients -= disconnected
        if disconnected:
            self.logger.info(f"Removed {len(disconnected)} disconnected WebSocket clients")

    async def handle_websocket_connection(self, websocket, path=None):
        """Handle new WebSocket connections - compatible with websockets 15.x and 16.x"""
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.logger.info(f"New WebSocket connection from {client_info}. Total clients: {len(self.connected_clients)}")
        
        # Add client AFTER logging but BEFORE starting tasks
        self.connected_clients.add(websocket)

        # Create a dedicated sending task for this client (like server.py)
        async def send_signals_to_client():
            # Wait a bit before starting to send signals to ensure handshake is complete
            await asyncio.sleep(1)
            while True:
                try:
                    # Always send current detection status
                    if self.all_objects:
                        # Calculate overall average confidence
                        total_confidence = sum(obj["confidence"] for obj in self.all_objects.values() if isinstance(obj, dict))
                        avg_confidence = total_confidence / len([obj for obj in self.all_objects.values() if isinstance(obj, dict)])
                        
                        # Create object summary
                        object_summary = []
                        for obj_name, obj_data in self.all_objects.items():
                            if isinstance(obj_data, dict):
                                object_summary.append(f"{obj_data['count']} {obj_name}(s) @{obj_data['confidence']:.2f}")
                            else:
                                object_summary.append(f"{obj_data} {obj_name}(s)")
                        
                        message = {
                            "alert": self.signal_active,  # True only for person+cup combo
                            "status": "active",
                            "timestamp": datetime.now().isoformat(),
                            "frame": self.frame_count,
                            "target_detection": self.current_detection,
                            "target_confidence": self.current_confidence,
                            "average_confidence": round(avg_confidence, 3),
                            "all_objects": self.all_objects,
                            "summary": ", ".join(object_summary),
                            "message": f"Detecting: {', '.join(object_summary)}"
                        }
                        await websocket.send(json.dumps(message))
                        if self.frame_count % 50 == 0:  # Reduce logging frequency
                            self.logger.debug(f"Status sent to {client_info}: {message['summary']}")

                    await asyncio.sleep(0.5)  # Send updates every 0.5 seconds
                except websockets.exceptions.ConnectionClosed:
                    self.logger.info(f"Connection closed while sending signals to {client_info}")
                    break
                except Exception as e:
                    self.logger.error(f"Error sending to {client_info}: {e}")
                    break

        # Start the sending task
        signal_task = asyncio.create_task(send_signals_to_client())

        try:
            # Handle incoming messages (like server.py)
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10)
                    self.logger.info(f"Received message from {client_info}: {message}")
                except asyncio.TimeoutError:
                    self.logger.debug(f"No message received from {client_info}, sending ping to keep connection alive")
                    await websocket.ping()

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"WebSocket connection from {client_info} closed normally")
        except Exception as e:
            self.logger.error(f"WebSocket error with {client_info}: {e}")
        finally:
            signal_task.cancel()  # Clean up the sending task
            self.connected_clients.discard(websocket)
            self.logger.info(f"Client {client_info} disconnected. Remaining clients: {len(self.connected_clients)}")

    async def start_websocket_server(self):
        """Start the WebSocket server"""
        self.logger.info("Starting WebSocket server on 0.0.0.0:6789")
        try:
            async with websockets.serve(
                self.handle_websocket_connection, 
                "0.0.0.0", 
                6789,
                ping_interval=20,  # Send ping every 20 seconds
                ping_timeout=10,   # Wait 10 seconds for pong
                close_timeout=10   # Wait 10 seconds for close
            ):
                self.logger.info("WebSocket server started successfully")
                await asyncio.Future()  # Run forever
        except Exception as e:
            self.logger.error(f"Failed to start WebSocket server: {e}")
            raise

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
