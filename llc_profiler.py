#!/usr/bin/python3
import lxc
import sys
import os
import io
import ast
import numpy as np

from time import time
from bitarray import bitarray
from bitarray.util import ba2hex
from system import File

THRESHOLD = 5

class LLCProfiler:
	def __init__(self, name, container, cmd_format, files, num_ways, core_id, number_of_runs):
		self.name = name
		self.container = container
		self.cmd_format = cmd_format
		self.files = files
		self.num_ways = num_ways
		self.core_id = core_id
		self.number_of_runs = number_of_runs
		self.profile = dict([(f.size, 1) for f in files])

		# 3-Dimensional output data type
		records = dict([(i, 0.0) for i in range(1, self.num_ways + 1)])
		self.results = dict([(f.size, records) for f in files])

	def run(self):
		for file in self.files:
			records = dict([(i, 0.0) for i in range(1, self.num_ways + 1)])
			for n in range(1, self.num_ways + 1):
				i = 0
				while (n + i) % 4 != 0:
					i = i + 1 
				mask = bitarray([0 for j in range(0, i)]) # Add zeros on the front if necessary so that the size of the table is a multiple of 4
				mask.extend([1 for j in range(0, n)])

				# Set LLC bitmask
				ec = os.system("pqos -I -e \"llc:1=0x{}\"".format(ba2hex(mask)))
				if ec:
					print("Unable to set llc capacity bitmask", file=sys.stderr)
					sys.exit(ec)
				
				ec = os.system("pqos -I -a \"llc:1={}\"".format(self.core_id))
				if ec:
					print("Unable to allocate COS to the specified CPU", file=sys.stderr)
					sys.exit(ec)

				# Run benchmark
				tmp = []
				for k in range(0, self.number_of_runs):
					start = time()
					self.container.attach_wait(lxc.attach_run_command, self.cmd_format.format(file.name).split(' '))
					end = time()
					tmp.append(end - start)
				
				# Save time record
				records[n] = np.percentile(tmp, 70)

			# Save records into array
			self.results[file.size] = records
		
		# Save results in the profile file
		with open("data/{}.llc.data".format(self.name), 'w+') as output:
			output.write(str(self.results))
			
		# Reset CAT configuration
		os.system("pqos -I -R")

	def load_data(self):
		data = open("data/{}.llc.data".format(self.name)).read()
		self.results = ast.literal_eval(data)
		#print(self.results)

	def profile_data(self):
		min_ways = dict()
		# Determine minimum number LLC ways needed
		for size in self.results:
			self.profile[size] = self.__get_min_ways(self.results[size])
		with open("profiles/{}.llc.profile".format(self.name), 'w+') as output:
			output.write(str(self.profile))
		print(self.profile)

	def load_profile(self):
		data = open("profiles/{}.llc.profile".format(self.name)).read()
		self.profile = ast.literal_eval(data)
		print(self.profile)

	def __get_min_ways(self, values):
		m = 1
		ref = values[self.num_ways]
		for n in range(2, self.num_ways + 1):
			delta = 100 * (values[n] - ref) / ref
			if delta > THRESHOLD:
				m = n
			#elif delta < -THRESHOLD:
			#   continue
		return m
