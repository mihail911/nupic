#!/bin/bash 

NUMSWARMS=3
for n in `seq 1 $NUMSWARMS`
do 
	./run_swarm.py permutations.py | tee swarmRun_$n.txt
done

rm permutations_*
