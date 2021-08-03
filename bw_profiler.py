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
from util import File

THRESHOLD = 0.75

class BWProfiler:
   def __init__(self, name, container, cmd_format, files, core_id, number_of_runs):
      self.name = name
      self.container = container
      self.cmd_format = cmd_format
      self.files = files
      self.core_id = core_id
      self.number_of_runs = number_of_runs
      self.profile = dict([(f.size, (10, 0.0)) for f in files])

      # 3-Dimensional output data type
      records = dict([(i, 0.0) for i in range(10, 101, 10)]) # beetwen 10% and 100%, with a step of 10%
      self.results = dict([(f.size, records) for f in files])

   def run(self):
      for file in self.files:
         records = dict([(i, 0.0) for i in range(10, 101, 10)])
         for n in range(10, 101, 10):
            # Set the maximum mandwidth
            ec = os.system("pqos -I -e \"mba:1={}\"".format(n))
            if ec:
               print("Unable to set  for the llc", file=sys.stderr)
               sys.exit(ec)
            
            ec = os.system("pqos -I -a \"core:1={}\"".format(self.core_id))
            if ec:
               print("Unable to allocate COS to the specified CPU", file=sys.stderr)
               sys.exit(ec)

            # Start benchmark
            tmp = []
            for k in range(0, self.number_of_runs):
               start = time()
               self.container.attach_wait(lxc.attach_run_command, self.cmd_format.format(file.name).split(' '))
               end = time()
               tmp.append(end - start)
            
            # Save time record
            records[n] = np.percentile(tmp, 50)

         # Save records into array
         self.results[file.size] = records
      
      # Save results in the profile file
      with open("data/{}.bw.data".format(self.name), 'w+') as output:
         output.write(str(self.results))
         
      # Reset CAT configuration
      os.system("pqos -I -R")

   def load_data(self):
      data = open("data/{}.bw.data".format(self.name)).read()
      self.results = ast.literal_eval(data)

   def profile_data(self):
      min_bw = dict()
      # Determine minimum number LLC ways needed
      for sz in self.results:
         delta = self.results[sz][10] - self.results[sz][20]
         self.profile[sz] = (self.__get_min_bw_limit(self.results[sz]), delta if delta > 0 else 0)
      with open("profiles/{}.bw.profile".format(self.name), 'w+') as output:
         output.write(str(self.profile))
      print(self.profile)

   def load_profile(self):
      data = open("profiles/{}.bw.profile".format(self.name)).read()
      self.profile = ast.literal_eval(data)

   def __get_min_bw_limit(self, values):
      m = 10
      for n in range(20, 101, 10):
         delta = values[m] - values[n]
         if delta > THRESHOLD:
            m = n
         elif delta < -THRESHOLD:
            continue
         else:
            break
      return m
   