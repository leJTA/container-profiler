#!/usr/bin/python3
import sys
import argparse
import os

import manager

# Parse command line arguments
parser = argparse.ArgumentParser(
   description="Launch a series of programs in container"
)
parser.add_argument("script_file", help="Script file")
args = parser.parse_args()
if not os.path.isfile(args.script_file) :
   print("{} : File not found".format(args.script_file), file=sys.stderr)
   sys.exit(1)

mngr = manager.Manager(args.script_file)
mngr.start()