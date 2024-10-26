BUILD_DIR = build
PCAP_DIR = pcaps
LOG_DIR = logs

P4C = p4c-bm2-ss

RUN_SCRIPT = utils/run_exercise.py

ifndef TOPO
TOPO = topology.json
endif

# Define DEFAULT_PROG to point to a specific P4 file
ifndef DEFAULT_PROG
DEFAULT_PROG = *.p4
endif

# Determine the directory of DEFAULT_PROG and set PROG_DIR accordingly
PROG_DIR = $(dir $(DEFAULT_PROG))

# Extract just the filename without the path
PROG_FILE = $(notdir $(DEFAULT_PROG))

# Define source files based on the determined PROG_DIR
source = $(wildcard $(PROG_DIR)/*.p4)
compiled_json := $(source:$(PROG_DIR)/%.p4=$(BUILD_DIR)/%.json)

# Determine default JSON files for run_args
DEFAULT_JSON = $(BUILD_DIR)/$(PROG_FILE:.p4=.json)

# Define NO_P4 to start BMv2 without a program
ifndef NO_P4
run_args += -j $(DEFAULT_JSON)
endif

# Set BMV2_SWITCH_EXE to override the BMv2 target
ifdef BMV2_SWITCH_EXE
run_args += -b $(BMV2_SWITCH_EXE)
endif

all: run

run: build
	sudo python3 $(RUN_SCRIPT) -t $(TOPO) $(run_args)

stop:
	sudo mn -c

build: dirs $(compiled_json)

# Compilation rule, outputting JSON and p4info files to BUILD_DIR
$(BUILD_DIR)/%.json: $(PROG_DIR)%.p4
	$(P4C) --p4v 16 --p4runtime-files $(BUILD_DIR)/$*.p4.p4info.txt -o $@ $<

dirs:
	mkdir -p $(BUILD_DIR) $(PCAP_DIR) $(LOG_DIR)

clean: stop
	rm -f $(PCAP_DIR)/*.pcap
	rm -rf $(BUILD_DIR) $(PCAP_DIR) $(LOG_DIR)
