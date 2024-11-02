import argparse

parser = argparse.ArgumentParser(description="Network Emulator")

parser.add_argument("-p", "--port", type=int, required=True, dest="port")
parser.add_argument("-f", "--filename", type=str, required=True, dest="fileName")
parser.add_argument("-q", "--queue_size", type=int, required=True, dest="queueSize")
parser.add_argument("-l", "--log", type=str, required=True, dest="logName")

args = parser.parse_args()