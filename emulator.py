import argparse
import sys
import socket
from datetime import datetime, timedelta

parser = argparse.ArgumentParser(description="Network Emulator")

parser.add_argument("-p", "--port", type=int, required=True, dest="port")
parser.add_argument("-f", "--filename", type=str, required=True, dest="fileName")
parser.add_argument("-q", "--queue_size", type=int, required=True, dest="queueSize")
parser.add_argument("-l", "--log", type=str, required=True, dest="logName")

args = parser.parse_args()

# check port numbers
if 2049 > args.port or args.port > 65536:
    print("Sender port out of range.")
    sys.exit()
if 2049 > args.port or args.port > 65536:
    print("Requester port out of range.")
    sys.exit()