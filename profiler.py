#!/usr/bin/python3
import lxc
import sys
import argparse
import configparser
import os
import llc_profiler
import bw_profiler

from time import time
from system import File


# Parse command line arguments
parser = argparse.ArgumentParser(
   description="Profile an LXC container to determine its minimum resource requirements (LLC ways, bandwidth, and bandwidth sensitivity)."
)
parser.add_argument("config_file", help="Configuration file")
args = parser.parse_args()
if not os.path.isfile(args.config_file):
   print("{} : File not found".format(args.config_file), file=sys.stderr)
   sys.exit(1)

# Read configuration file
config = configparser.ConfigParser()
config.read(args.config_file)

# Read program name
program_name = config['main']['program_name']

# Check if container exists
container = lxc.Container(config['main']['container_name'])
if not container.defined:
   print("{} : container does not exist.".format(container.name), file=sys.stderr)
   sys.exit(1)

if not container.running:
   print("Container is not running, Starting container.")
   if not container.start():
      print("Failed to start container", file=sys.stderr)
      sys.exit(1)

# get command format and input file list
cmd_format = config['main']['command_format']
input_files = config['main']['input_files'].split(',')

# Read file sizes
fd = open("/tmp/tmp_profiler.txt", "w+")
for f in input_files:
   ec = container.attach_wait(lxc.attach_run_command, "stat -c %s {}".format(f).split(' '), stdout=fd)
   if ec:
      print("{} : Unable to get file size".format(f), file=sys.stderr)
      fd.close()
      sys.exit(ec)
fd.close()
fd = open("/tmp/tmp_profiler.txt", "r")
input_sizes = fd.readlines()
files = [File(input_files[i], int(input_sizes[i])) for i in range(0, len(input_files))]

# Read the maximum number of ways
num_ways = int(config['main']['number_of_ways'])

# Read the processor number
core_id = str( container.get_config_item("lxc.cgroup.cpuset.cpus")[0] )
if core_id == "0":
   print("Warning! The container is pined to the core 0. this is not good for bandwidth profiling!!")
   exit(1)

# Read the number of runs per case
number_of_runs = int(config['main']['number_of_runs'])

# Start LLC usage profiling
p = llc_profiler.LLCProfiler(program_name, container, cmd_format, files, num_ways, core_id, number_of_runs)
#p.run()
p.load_data()
p.profile_data()
# p.load_profile()

# Start Bandwidth usage profiling
p = bw_profiler.BWProfiler(program_name, container, cmd_format, files, core_id, number_of_runs)
#p.run()
# p.load_data()
#p.profile_data()
# p.load_profile()
# FINISHED
print ("[ Finished ]")