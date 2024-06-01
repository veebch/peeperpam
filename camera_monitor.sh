#!/bin/bash

# Ensure to replace 'your_command' with the actual command you want to monitor
your_command 2>&1 | grep --line-buffered -E 'Object.*person|person.*Object' | while IFS= read -r line; do
    last_relevant_line=$line
    echo -ne "\r\033[K$last_relevant_line"
done &

# Initialize variables
prev_line=""
output_file="objects.txt"

# Monitor the relevant lines and write to file every 0.1 seconds
while true; do
  # Capture the current relevant line from the background process
  current_line=$last_relevant_line

  # Check if the current line is different from the previous line
  if [ "$current_line" != "$prev_line" ]; then
    echo "$current_line" > "$output_file"
    prev_line="$current_line"
  else
    echo "No Objects" > "$output_file"
  fi

  # Wait for 0.1 seconds
  sleep 0.1
done
