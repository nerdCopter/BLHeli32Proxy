#!/bin/bash
# One-time per boot: load usbmon so the capture device node exists.
set -e
sudo modprobe usbmon
ls -la /dev/usbmon1
