#!/bin/bash

# Temporary file to store the latest relevant line
temp_output_file="temp_output.txt"

# Function to clean up temporary files and kill the background process on exit
cleanup() {
  echo "Cleaning up..."
  rm -f "$temp_output_file"
  if ps -p "$bg_pid" > /dev/null 2>&1; then
    echo "Killing background process $bg_pid"
    kill "$bg_pid"
  fi
  pkill -P $$  # Kill all child processes of this script
  echo "Cleanup complete"
  exit 0
}
trap cleanup EXIT INT TERM

# Initialize the temporary file
: > "$temp_output_file"

# Run the command in the background and pipe the output to grep, storing the latest line in the temporary file
rpicam-hello -n -v 2 -t 0 --post-process-file /home/pi/rpicam-apps/assets/hailo_yolo8_inference.json --lores-width 640 --lores-height 640 2>&1 | grep --line-buffered -E 'Object.*person|person.*Object' | while IFS= read -r line; do
  echo "$line" > "$temp_output_file"
done &

# Store the PID of the background process
bg_pid=$!
echo "Background process ID: $bg_pid"

# Initialize variables
prev_line=""
output_file="objects.txt"

# Monitor the relevant lines and write to file every 0.1 seconds
while true; do
  # Read the last relevant line from the temporary file
  if [ -s "$temp_output_file" ]; then
    current_line=$(cat "$temp_output_file")
  else
    current_line=""
  fi

  # Check if the current line is different from the previous line
  if [ "$current_line" != "$prev_line" ]; then
    echo "$current_line" > "$output_file"
    echo "Updated objects.txt with: $current_line"
    prev_line="$current_line"
  else
    echo "No Objects" > "$output_file"
  fi

  # Wait for 0.1 seconds
  sleep 0.1
done
