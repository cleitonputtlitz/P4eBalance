BMV2_SWITCH_EXE = simple_switch_grpc
TOPO = configs/fat-tree/topology.json
DEFAULT_PROG = switches/basic.p4
P4C_ARGS = -D COLLECT_SIZE=0
#-D FREQ=50000
#FREQ=50000 50ms
#noINT 281474976710655

include utils/Makefile
