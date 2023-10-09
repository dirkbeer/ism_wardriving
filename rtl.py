#!/usr/bin/env python3

"""Read events from rtl_433 and gpsd and save to a JSON file."""

import os
import sys
import subprocess
import socket
import json
from datetime import datetime
import psutil
import signal

os.system('bash -c "source ~/.bashrc"')

# -c option
CONF_FILE = 'rtl.conf'  

# Current date and time to append to the JSON filename
current_datetime_str = datetime.now().strftime('%Y%m%d_%H%M%S')

DATA_DIR = "/home/sdr/ism_wardriving/data"
JSON_FILENAME = os.path.join(DATA_DIR, f'rtl_{current_datetime_str}.json')

# Check if the data directory exists, if not, create it
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# get the rtl_433 path so that this works no matter if using the package or compiling from source
try:
    result = subprocess.run(['which', 'rtl_433'], capture_output=True, text=True, check=True)
    RTL_433_PATH = result.stdout.strip()
except subprocess.CalledProcessError:
    RTL_433_PATH = "/usr/bin/rtl_433"

# rtl_433 syslog address
UDP_IP = "127.0.0.1"
UDP_PORT = 1514

def parse_syslog(line):
    """Try to extract the payload from a syslog line."""
    line = line.decode("ascii")
    if line.startswith("<"):
        fields = line.split(None, 7)
        line = fields[-1]
    return line

def report_event(data, file_handle):
    """Save an rtl_433 event to a JSON file."""

    if not data.get("model"):
        return

    # Append the data to the JSON file
    json.dump(data, file_handle)
    file_handle.write("\n")
    file_handle.flush()

if __name__ == '__main__':

    # reset SDRPlay in case it's gotten hung up
    os.system('/usr/local/bin/restartSDRplay')

    # start the rtl_433 monitoring process 
    rtl_process = subprocess.Popen([RTL_433_PATH, '-c', CONF_FILE], stdout=subprocess.PIPE, text=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind((UDP_IP, UDP_PORT))

    try:
        # Open JSON file in write mode
        with open(JSON_FILENAME, 'w') as file:
            while True:
                line, addr = sock.recvfrom(1024)
                try:
                    line = parse_syslog(line)
                    data = json.loads(line)
                    report_event(data, file)

                except (KeyError, ValueError) as e:
                    print(f"An error occurred: {e}")

    except (KeyboardInterrupt, SystemExit):  # when you press ctrl+c
        print("\nAborted. Exiting...")

    except Exception as e:  # Handle other unexpected exceptions
        print(f"An error occurred: {e}")

    finally:
        sock.close()
        rtl_process.send_signal(signal.SIGINT)
        rtl_process.wait()

    print("Done.\n")
