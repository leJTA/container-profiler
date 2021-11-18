#/bin/bash

sudo pqos -I -R
rm results.csv
rm info.log

for i in $(seq 0 9)
do
   echo "Execution number $i"
   python3 run.py $1
   cat out.csv >> results.csv
   echo -n "\n" >> results.csv
   rm out.csv
done