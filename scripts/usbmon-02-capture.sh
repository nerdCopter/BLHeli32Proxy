#!/bin/bash
# Live capture on bus 1 (PyroDrone F7 / STM32F7X2, /dev/ttyACM1). Ctrl+C to stop.
# Chown chained in so the file is yours to read immediately after.
set -e
sudo tshark -i usbmon1 -w /tmp/blheli-usb-capture.pcapng
sudo chown "$USER:$USER" /tmp/blheli-usb-capture.pcapng
