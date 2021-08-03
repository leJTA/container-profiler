import os
import sys
import logging
import numpy as np

from bitarray import bitarray
from bitarray.util import hex2ba, ba2hex

TRASHING_WAYS = 3

class File:
   def __init__(self, name, size):
      self.name = name
      self.size = size

class Action:
   def __init__(self, container_name, program_name, cmd, input_filesize):
      self.container_name = container_name
      self.program_name = program_name
      self.cmd = cmd
      self.input_filesize = input_filesize
      self.required_ways = 1
      self.bw_usage = 10 # in %
      self.bw_sensitivity = 0
      self.is_trashing = False

class PlanningEntry:
   def __init__(self, time, action):
      self.time = time
      self.action = action


class BW:
   def __init__(self, num_cos):
      self.occupancy = 0
      self.num_cos = num_cos

class Way:
   def __init__(self, id, llc):
      self.id = id
      self.llc = llc
      self.stress_value = 0

   def __str__(self):
      return ""

class COS:
   def __init__(self, id):
      self.id = id
      self.mask = hex2ba("7ff")
      self.ways = []

   def stress_value(self):
      val = 0
      for w in self.ways:
         val += w.stress_value
      return val

class LLC:
   def __init__(self, id, num_ways, num_cos):
      self.id = id
      self.ways = [Way(i, self) for i in range(0, num_ways)]
      self.cos = [COS(i) for i in range(0, num_cos)]
      
      self.init_cos(num_cos)

   def init_cos(self, num_cos):
      if (len(self.ways) == 11 and num_cos == 8):
         self.cos[0].mask = hex2ba("600")
         self.cos[1].mask = hex2ba("1e0")
         self.cos[2].mask = hex2ba("7f0")
         self.cos[3].mask = hex2ba("7fc")
         self.cos[4].mask = hex2ba("7ff")
         self.cos[5].mask = hex2ba("4")
         self.cos[6].mask = hex2ba("2")
         self.cos[7].mask = hex2ba("1")

         self.cos[0].ways = self.ways[0:2]
         self.cos[1].ways = self.ways[2:6]
         self.cos[2].ways = self.ways[0:7]
         self.cos[3].ways = self.ways[0:9]
         self.cos[4].ways = self.ways[0:11]
         self.cos[5].ways = self.ways[8:9]
         self.cos[6].ways = self.ways[9:10]
         self.cos[7].ways = self.ways[10:11]

         for c in self.cos:
            assert(c.mask.count() == len(c.ways))
         #print([c.mask for c in self.cos])



   def increase_stress(self, cos_id, load):
      avg_load = load / len(self.cos[cos_id])
      for w in self.cos[cos_id].ways:
         w.stress_value += avg_load

   def decrease_stress(self, cos_id, load):
      avg_load = load / len(self.cos[cos_id])
      for w in self.cos[cos_id].ways:
         w.stress_value -= avg_load

   def stress_value(self):
      val = 0
      for w in self.ways[:-TRASHING_WAYS]:
         val += w.stress_value
      return val

   def trashing_stress_value(self):
      val = 0
      for w in self.ways[-TRASHING_WAYS:]:
         val += w.stress_value
      return val

class SystemState:
   def __init__(self, num_llc, num_ways, num_cos):
      self.llcs = [LLC(i, num_ways=num_ways, num_cos=num_cos) for i in range(0, num_llc)]
      self.bw = BW(num_cos=num_cos)
      self.num_cos = num_cos
      self.map = dict()

      for llc in self.llcs:
         for cos in llc.cos:
            ec = os.system("pqos -I -e \"llc@{}:{}=0x{}\"".format(llc.id, cos.id, ba2hex(cos.mask)))
            if ec:
               print("Unable to set llc capacity bitmask", file=sys.stderr)
               sys.exit(ec)

   def get_smart_allocation(self, action):
      # firstly, get the least stressed cache
      selected_llc = self.llcs[0]
      if action.is_trashing:
         for llc in self.llcs:
            if selected_llc.trashing_stress_value() < llc.trashing_stress_value():
               selected_llc = llc
      else:
         for llc in self.llcs:
            if selected_llc.stress_value() < llc.stress_value():
               selected_llc = llc

      # Secondly, get the COS giving the lowest(greater than 1) load_per_way
      lpw = -1
      for i in range(0, self.num_cos):
         current_lpw = (action.required_ways + selected_llc.cos[i].stress_value()) / selected_llc.cos[i].mask.count() # or len(cos.ways)
         if lpw > current_lpw or lpw < 0:
            lpw = current_lpw
            if lpw < 1:
               return i
      return selected_llc.id, i

   def update_system_state(self, llc_id, cos_id, action):
      cos = self.llcs[llc_id].cos[cos_id]
      for w in cos.ways:
         w.stress_value += action.required_ways / cos.mask.count()

   def on_new_action(self, action):
      llc_id, cos_id = self.get_smart_allocation(action)
      print(llc_id, cos_id)
      # TODO allocate cos
      self.update_system_state(llc_id, cos_id, action)

   def on_action_finished(self, action):
      # TODO update system state
      pass