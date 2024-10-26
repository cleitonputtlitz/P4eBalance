#!/usr/bin/env python3
import sys
import os
from scapy.all import *
import csv
import time
from scapy.packet import Packet, bind_layers
#from save_metrics import *
from collections import OrderedDict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pkt_gen.headers import *

# Dictionary to store metrics
switch_metrics = {}
host_metrics = {}

last_switch_metrics = {}

# Intervalo de tempo para gravar os dados no arquivo (em segundos)
flush_interval = 10
last_flush_time = None  # Para controle do tempo entre gravações

# Inicializa os valores de 'q_delay', 'q_depth' e 'q_drops' com 0
for swid in range(0, 10):
    switch_metrics[swid] = {
        'q_delay': 0,
        'q_depth': 0,
        'q_drops': 0
    }
    last_switch_metrics[swid] = {
        'q_depth': []
    }
for h in range(5, 6):
    host_metrics[h] = {
        "cpu": 0
    }

tot_pkt_rec = 0

csv_writer = None
csv_file = None

# Conectar ao servidor Redis
#r = redis.StrictRedis(host='localhost', port=6379, db=0)

def iniciar_csv():
    global csv_writer, csv_file, last_flush_time
    csv_file = open('../experiments/metrics_log.csv', mode='w', newline='')    #sobrescrever
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["time","path_id",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "sw_id", "q_delay", "q_depth", "drops",
                    "h_id", "CPU_Occupancy"])

    last_flush_time = time.time()

def finalizar_csv():
    global csv_file
    if csv_file:
        csv_file.close()

def process_INT_Packet(pkt_INT):
    global tot_pkt_rec, csv_writer, csv_file, last_flush_time
    tot_pkt_rec += 1

    packet = Ether(pkt_INT.packet.payload)
    #packet.show2()

    path_id = None
    linha_csv = []

    if int_host in packet and LB_path in packet and int_header in packet:
        lb_path_layer = packet[LB_path]
        path_id = lb_path_layer.path_id
        #print(f"LB_path path_id: {lb_path_layer.path_id}")
        linha_csv.extend([time.time(), path_id])

        qtd_traces = packet[int_header].qtd_traces

        trace_data = {}
        current_layer = packet.getlayer(int_trace)
        while current_layer is not None:
            swid    = current_layer.swid
            q_delay = current_layer.q_delay
            q_depth = current_layer.q_depth
            q_drops = current_layer.q_drops

            linha_csv.extend([swid, q_delay, q_depth, q_drops])

            if swid in trace_data:
                trace_data[swid]['q_delay'] = max(trace_data[swid]['q_delay'], q_delay)
                trace_data[swid]['q_depth'] = max(trace_data[swid]['q_depth'], q_depth)
                trace_data[swid]['q_drops'] = max(trace_data[swid]['q_drops'], q_drops)
            else:
                trace_data[swid] = {
                    'q_delay': q_delay,
                    'q_depth': q_depth,
                    'q_drops': q_drops
                }

            current_layer = current_layer.payload if isinstance(current_layer.payload, int_trace) else None

        for swid, current_data in trace_data.items():
            if swid in switch_metrics:
                switch_metrics[swid]['q_delay'] = current_data['q_delay']
                switch_metrics[swid]['q_depth'] = current_data['q_depth']
                switch_metrics[swid]['q_drops'] = current_data['q_drops']
            else:
                # Se não existir, insere o swid e seus dados no dicionário global
                switch_metrics[swid] = current_data

            # ultimas metricas para cada switch
            last_switch_metrics[swid]['q_depth'].append(switch_metrics[swid]['q_depth'])


            if len(last_switch_metrics[swid]['q_depth']) > 10:
                last_switch_metrics[swid]['q_depth'].pop()

        int_host_layer = packet.getlayer(int_host)
        host_id = int_host_layer.hid
        cpu = int_host_layer.cpu

        linha_csv.extend([host_id, cpu])

        #print(f" int_host_layer.hid {int_host_layer.hid} int_host_layer: {int_host_layer.cpu}")

        host_metrics[host_id] = {
            "cpu": cpu
        }

        #for swid, metrics in last_switch_metrics.items():
        #    print(f"Switch ID: {swid}: {list(metrics['q_depth'])}")

        print(f'linha_csv {linha_csv}')

        csv_writer.writerow(linha_csv)

        current_time = time.time()
        if current_time - last_flush_time >= flush_interval:
            csv_file.flush()
            last_flush_time = current_time
