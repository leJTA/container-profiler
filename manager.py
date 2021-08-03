#!/usr/bin/python3
import lxc
import sys
import argparse
import configparser
import os
import ast
import sched
import time
import numpy as np

from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LinearRegression
from system import Action, LLC, PlanningEntry, SystemState

NUMBER_OF_NEIGHBORS = 1
NUMBER_OF_LLC = 2
NUMBER_OF_WAYS = 11
NUMBER_OF_COS = 8
THRESHOLD = 1

class Manager:
   def __init__(self, script_file):
      self.llc_profiles = dict()
      self.bw_profiles = dict()
      self.predictors = dict() # map <prediction_type, program_name, value>
      self.planning = [] # list <time, action>
      self.scheduler = sched.scheduler(time.time, time.sleep)
      self.system_state = SystemState(num_llc=NUMBER_OF_LLC, num_ways=NUMBER_OF_WAYS, num_cos=NUMBER_OF_COS)

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
         self.predictors["llc_ways"][pname] = KNeighborsClassifier(NUMBER_OF_NEIGHBORS)
         self.predictors["llc_ways"][pname].fit(data, target)

      #Bandwidth sensitivity predictor (LinearRegression)
      for pname in self.llc_profiles:
         data = np.array([k for k in self.bw_profiles[pname]]).reshape(-1, 1)
         target = np.array([self.bw_profiles[pname][k][1] for k in self.bw_profiles[pname]])
         self.predictors["bw_sens"][pname] = LinearRegression()
         self.predictors["bw_sens"][pname].fit(data, target)

   def execute_action(self, id):
      # Predict values
      self.planning[id].action.required_ways = self.predictors["llc_ways"][self.planning[id].action.program_name].predict([[self.planning[id].action.input_filesize]])
      self.planning[id].action.bw_sensitivity = self.predictors["bw_sens"][self.planning[id].action.program_name].predict([[self.planning[id].action.input_filesize]])
      if (self.planning[id].action.required_ways == 1 and self.planning[id].action.bw_sensitivity > THRESHOLD):
         self.planning[id].action.is_trashing = True

      #print("predicted values : number of llc ways = {}, bandwidth sensitivity = {}".format(self.planning[id].action.required_ways, self.planning[id].action.bw_sensitivity))
      print(self.planning[id].action.bw_sensitivity)
      
      # TODO launch containers in threads
      

   def start(self):
      #self.get_profiles()
      #self.fit()
      #self.scheduler.run()
      pass