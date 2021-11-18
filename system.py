import os
import sys
import threading
import logging
import numpy as np

from bitarray import bitarray
from bitarray.util import hex2ba, ba2hex

TRASHING_WAYS = 3
TRASHING_COS = 3
NO_CAT = True
SMART_SOCKET_SELECTION = True

lock = threading.Lock()

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
			self.cos[0].mask = hex2ba("600")	# AA000000000
			self.cos[1].mask = hex2ba("1e0")	# 00AAAA00000
			self.cos[2].mask = hex2ba("7f0")	# AAAAAAA0000
			self.cos[3].mask = hex2ba("7fc")	# AAAAAAAAA00
			self.cos[4].mask = hex2ba("7ff")	# AAAAAAAAAAA
			self.cos[5].mask = hex2ba("4")	# 00000000A00
			self.cos[6].mask = hex2ba("2")	# 000000000A0
			self.cos[7].mask = hex2ba("1")	# 0000000000A

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
		for w in self.ways:
			val += w.stress_value
		return val

	def trashing_stress_value(self):
		val = 0
		for w in self.ways[-TRASHING_WAYS:]:
			val += w.stress_value
		return val

class Socket:
	def __init__(self, cpus):
		self.cpus = cpus
		self.used_cpus = []

class ResAllocation:
	def __init__(self, llc_id, cpu_id, cos_id):
		self.llc_id = llc_id
		self.cpu_id = cpu_id
		self.cos_id = cos_id

	def __str__(self):
		return "<llc_id={}, cpu_id={}, cos_id={}>".format(self.llc_id, self.cpu_id, self.cos_id)

	__repr__ = __str__

class System:
	def __init__(self, num_sockets, num_ways, num_cos):
		self.sockets = [Socket([]) for i in range(num_sockets)]
		self.llcs = [LLC(i, num_ways=num_ways, num_cos=num_cos) for i in range(num_sockets)]
		self.bw = BW(num_cos=num_cos)
		self.num_cos = num_cos
		self.map = dict()

		if num_sockets == 2:
			self.sockets[0].cpus = [0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38]
			self.sockets[1].cpus = [1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39]
		
		if NO_CAT:
			return

		for llc in self.llcs:
			for cos in llc.cos:
				ec = os.system("pqos -I -e \"llc@{}:{}=0x{}\"".format(llc.id, cos.id, ba2hex(cos.mask)))
				if ec:
					print("Unable to set llc capacity bitmask", file=sys.stderr)
					sys.exit(ec)

	def get_smart_allocation(self, action):
		selected_llc = self.llcs[0]

		if SMART_SOCKET_SELECTION:
			# Get the least stressed cache
			selected_llc = self.llcs[0]
			if action.is_trashing:
				for llc in self.llcs:
					if selected_llc.trashing_stress_value() > llc.trashing_stress_value():
						selected_llc = llc
			else:
				for llc in self.llcs:
					if selected_llc.stress_value() > llc.stress_value():
						selected_llc = llc
		else:
			for id in range(len(self.llcs)):
				if len(self.sockets[id].used_cpus) < len(self.sockets[selected_llc.id].used_cpus):
					selected_llc = self.llcs[id]

		# Get the COS giving the lowest(greater than 1) load_per_way
		if action.is_trashing: # then we take [N - ntrash, N[
			start = self.num_cos - TRASHING_COS
			end = self.num_cos
		else: # else we take [0, N - ntrash[
			start = 0
			end = self.num_cos - TRASHING_COS

		lpw = -1       # Load Per Way
		cos_id = start
		for i in range(start, end):
			current_lpw = (action.required_ways + selected_llc.cos[i].stress_value()) / selected_llc.cos[i].mask.count()
			if lpw > current_lpw or lpw < 0:
				lpw = current_lpw
				cos_id = i
				if lpw <= 1:
					break
		return selected_llc.id, cos_id

	def on_new_action(self, action):
		llc_id, cos_id = self.get_smart_allocation(action)

		lock.acquire()
		cpu_id = self.sockets[llc_id].cpus.pop()
		self.sockets[llc_id].used_cpus.append(cpu_id)
		lock.release()
		
		self.map[action] = ResAllocation(llc_id, cpu_id, cos_id)
		cos = self.llcs[llc_id].cos[cos_id]
		
		lock.acquire()
		for w in cos.ways:
			w.stress_value +=  action.required_ways / cos.mask.count()
		lock.release()
      
		if NO_CAT:
			return

		ec = os.system("sudo pqos -I -a \"llc:{}={}\"".format(cos_id, cpu_id))
		if ec:
			print("Unable to allocate COS{} to CPU{}".format(cos_id, cpu_id), file=sys.stderr)
			sys.exit(ec)


	def on_action_finished(self, action):
		llc_id = self.map[action].llc_id
		cpu_id = self.map[action].cpu_id
		cos_id = self.map[action].cos_id
		
		lock.acquire()
		self.sockets[llc_id].cpus.append(cpu_id)
		self.sockets[llc_id].used_cpus.remove(cpu_id)
		lock.release()

		if NO_CAT:
			return

		lock.acquire()
		cos = self.llcs[llc_id].cos[cos_id]
		for w in cos.ways:
			w.stress_value -= action.required_ways / cos.mask.count()
		lock.release()

	def state(self):
		s = ""
		for llc in self.llcs:
			s += str([round(w.stress_value, 2) for w in llc.ways])

		return s