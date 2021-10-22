#!/usr/bin/python3
import threading
import logging
import concurrent.futures
import lxc
import sys
import os
import ast
import sched
import time
import numpy as np

from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LinearRegression
from system import NO_CAT, Action, LLC, PlanningEntry, System

logging.basicConfig(level=logging.INFO, filename='info.log')

KNN_NUMBER_OF_NEIGHBORS = 1
NUMBER_OF_SOCKETS = 2
NUMBER_OF_WAYS = 11
NUMBER_OF_COS = 8
TIME_THRESHOLD = 5

class Manager:
	def __init__(self, script_file):
		self.llc_profiles = dict()
		self.bw_profiles = dict()
		self.predictors = dict() # map <prediction_type, program_name, value>
		self.system = System(num_sockets=NUMBER_OF_SOCKETS, num_ways=NUMBER_OF_WAYS, num_cos=NUMBER_OF_COS)
		self.planning = [] # list <time, action>
		self.scheduler = sched.scheduler(time.time, time.sleep)
		self.futures = []
		self.executor = concurrent.futures.ThreadPoolExecutor()
		self.results = dict()

		file = open(script_file, 'r')
		for line in file.readlines():
			if line[0] == "#":
				continue
			line = line.strip('\n') # Remove the trailing '\n'
			container_name = line.split(';')[0]
			launch_time = line.split(';')[1]
			program_name = line.split(';')[2]
			command_format = line.split(';')[3]
			input_filename = line.split(';')[4]

			self.results[container_name] = 0

			# get file size
			container = lxc.Container(container_name)
			if not container.defined:
				print("{} : container does not exist.".format(container_name), file=sys.stderr)
				sys.exit(1)
			
			if not container.running:
				if not container.start():
					print("Failed to start container", file=sys.stderr)
					sys.exit(1)

			fd = open("/tmp/tmp_manager.txt", "w")
			ec = container.attach_wait(lxc.attach_run_command, "stat -c %s {}".format(input_filename).split(' '), stdout=fd)
			if ec:
				print("{} : Unable to get file size".format(input_filename), file=sys.stderr)
				fd.close()
				sys.exit(ec)

			fd.close()

			fd = open("/tmp/tmp_manager.txt", "r")
			input_filesize = int(fd.readline().strip())
			fd.close()
			
			# Store informations in Action object
			action = Action(container_name, program_name, command_format.format(input_filename), input_filesize)
			self.planning.append(PlanningEntry(float(launch_time), action))
			
		for i in range(0, len(self.planning)):
			self.scheduler.enter(self.planning[i].time, 1, self.execute_action, argument=(i,))

	def get_profiles(self):
		for (dirpath, dirnames, filenames) in os.walk("profiles/"):
			for fname in filenames:
				if fname.endswith(".llc.profile"):
					pname = fname.split(".")[0]
					pdata = open(dirpath + fname).read()
					self.llc_profiles[pname] = ast.literal_eval(pdata)

				elif fname.endswith(".bw.profile"):
					pname = fname.split(".")[0]
					pdata = open(dirpath + fname).read()
					self.bw_profiles[pname] = ast.literal_eval(pdata)

	def fit(self):
		self.predictors["llc_ways"] = dict()
		self.predictors["bw_sens"] = dict()

		#LLC Ways predictor (KNN classifier)
		for pname in self.llc_profiles:
			data = np.array([k for k in self.llc_profiles[pname]]).reshape(-1, 1)
			target = np.array([self.llc_profiles[pname][k] for k in self.llc_profiles[pname]])
			self.predictors["llc_ways"][pname] = KNeighborsClassifier(KNN_NUMBER_OF_NEIGHBORS)
			self.predictors["llc_ways"][pname].fit(data, target)

		#Bandwidth sensitivity predictor (LinearRegression)
		for pname in self.llc_profiles:
			data = np.array([k for k in self.bw_profiles[pname]]).reshape(-1, 1)
			target = np.array([self.bw_profiles[pname][k][1] for k in self.bw_profiles[pname]])
			self.predictors["bw_sens"][pname] = LinearRegression()
			self.predictors["bw_sens"][pname].fit(data, target)

	def exec_action(self, container, action):
		start = time.time()
		container.attach_wait(lxc.attach_run_command, action.cmd.split(' '))
		end = time.time()

		self.system.on_action_finished(action)
		self.results[action.container_name] = round(end - start, 2)
		logging.info("[Action on container {} finished] {} in {} seconds : system state = {}".format(action.container_name, action.program_name, end - start, self.system.state()))
		return end - start

	def execute_action(self, id):
		# Predict values
		action = self.planning[id].action
		action.required_ways = self.predictors["llc_ways"][action.program_name].predict([[action.input_filesize]])[0]
		action.bw_sensitivity = self.predictors["bw_sens"][action.program_name].predict([[action.input_filesize]])[0]
		if self.planning[id].action.required_ways == 1 and (action.bw_sensitivity > TIME_THRESHOLD):
			self.planning[id].action.is_trashing = True

		# New action event management function
		self.system.on_new_action(action)
		c = lxc.Container(action.container_name)
		#if NO_CAT: # If no CAT optimisation then we let the system schedule the containers over the cpus
		#	ec = os.system("lxc-cgroup -n {} cpuset.cpus 0-39".format(c.name))
		#else:
		ec = os.system("lxc-cgroup -n {} cpuset.cpus {}".format(c.name, self.system.map[action].cpu_id))
		if ec:
			print("Unable to set cpuset for container".format(c.name), file=sys.stderr)
			sys.exit(ec)

		logging.info("[New action] {} on container {} : system state = {}".format(action.program_name, action.container_name, self.system.state()))
		#TODO launch container in new thread
		self.futures.append(self.executor.submit(self.exec_action, c, action))

	def save_results(self):
		fd = open("out.csv", "w")
		fd.write(",".join([str(self.results[k]) for k in self.results]))
		fd.close()

	def start(self):
		self.get_profiles()
		self.fit()

		for id in range(len(self.planning)):
			action = self.planning[id].action
			required_ways = self.predictors["llc_ways"][action.program_name].predict([[action.input_filesize]])[0]
			print("id = {}, filesize = {}, required_ways = {}".format(id, action.input_filesize, required_ways))
		return

		self.scheduler.run()

		for future in concurrent.futures.as_completed(self.futures):
			print(future.result())

		self.save_results()