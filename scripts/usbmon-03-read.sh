#!/bin/bash
# Read back the capture. No sudo needed (file already chowned by usbmon-02-capture.sh).
set -e
tshark -r /tmp/blheli-usb-capture.pcapng
