#!/bin/bash

# Directory where the recordings will be saved
SAVE_DIR="$XDG_VIDEOS_DIR/Recordings"
mkdir -p "$SAVE_DIR"

# If gpu-screen-recorder is already running, send SIGINT to stop it properly
if pgrep -f "gpu-screen-recorder" >/dev/null; then
    pkill -SIGINT -f "gpu-screen-recorder"

    # Wait a moment to ensure the recording has stopped and the file is ready
    sleep 1

    # Get the latest recorded file
    LAST_VIDEO=$(ls -t "$SAVE_DIR"/*.mp4 2>/dev/null | head -n 1)

    # Notification with actions: "View" opens the file, "Open folder" opens the folder
    ACTION=$(notify-send -a "Hyprfabricated" "⬜ Recording started" \
        -A "view=View" -A "open=Open folder")

    if [ "$ACTION" = "view" ] && [ -n "$LAST_VIDEO" ]; then
        xdg-open "$LAST_VIDEO"
    elif [ "$ACTION" = "open" ]; then
        xdg-open "$SAVE_DIR"
    fi
    exit 0
fi

# Output file name for the new recording
OUTPUT_FILE="$SAVE_DIR/$(date +%Y-%m-%d-%H-%M-%S).mp4"

# Start recording
notify-send -a "Hyprfabricated" "🔴 Recording started"
gpu-screen-recorder -w screen -ac opus -cr full -a default_output -f 60 -fm vfr -encoder gpu -o "$OUTPUT_FILE"
