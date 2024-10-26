#!/usr/bin/env python3
import argparse
import os
import sys
from time import sleep
import json
import yaml
import grpc
import threading
import queue
from scapy.all import *

from topology import *
from headers_send import *
from engine_INT import *
from server import *
from utils import *

CPU_PORT = 255
packet_queue = queue.Queue()
current_paths = {}

def processPacketIn(sw):
    print('init processPacketIn ', sw.name )
    while True:
        try:
            packetin = sw.PacketIn()  # Blocking call, waits for a packet
            if packetin is not None:
                #print(f"Packtet INT received from {sw.name}")
                #print(packetin)
                packet_queue.put(packetin)
                #process_INT_Packet(packetin)
                #pkt = Ether(packetin.packet.payload)
                #pkt.show2()

        except grpc.RpcError as e:
            printGrpcError(e)
            break  # Exit the loop if there's an RPC error

# Process INT packet
def packetProcessor():
    iniciar_csv()
    try:
        while True:
            try:
                packetin = packet_queue.get()  # Blocking call
                if packetin is None:
                    sleep(0.01)
                    continue

                process_INT_Packet(packetin)
                packet_queue.task_done()  # Indica que o processamento do pacote foi concluído
            except Exception as e:
                print(f"Error in packetProcessor: {e}")
    finally:
        finalizar_csv()

def sendPacketOut(p4info_helper, sw, paths):
    print('sendPacketOut')
    path_weight=3
    pkt = b""

    for path in paths:
        pkt = pkt / active_path(path_id=path,path_weight=3)


    #pkt = active_path(path_id=2,path_weight=3) / active_path(path_id=3,path_weight=3) / active_path(path_id=4,path_weight=3) / active_path(path_id=5,path_weight=3)
    #pkt.show2()

    num_paths = len(paths)

    packetout = p4info_helper.buildPacketOut(
                            payload = bytes(pkt),
                            metadata = {
                                1: num_paths.to_bytes(1, 'big') # b"\003"
                                #2: "\000\001"
                            }
                        )
    sw.PacketOut(packetout,port=CPU_PORT)
    print('sendPacketOut done')

def get_initial_paths(paths, source, destination):
    if (source, destination) in paths:
        caminhos = paths[(source, destination)]
        print(f'caminhos de {source} para {destination} e {caminhos[0]} e {caminhos[5]}')
        #caminhos_aleatorios = random.sample(caminhos, 2)
        caminhos_aleatorios = [caminhos[0], caminhos[5]]
        return (caminhos_aleatorios[0][0], caminhos_aleatorios[1][0])
    else:
        return None

def main(p4info_file_path, bmv2_file_path, topo_file_path):
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    paths, port_mapping, switches_conected_to_client, switches_conected_to_server = topology_init(topo_file_path)

    switches_conf = load_switches_conf()
    hosts_conf = load_hosts_conf()
    hosts_server_1 = [host for host in hosts_conf['hosts'] if host['server'] == 1]

    threads = []
    try:
        switches = connect_to_switches(switches_conf["switches"])

        send_master_arbitration_updates(switches)

        set_pipelines(switches, p4info_helper, bmv2_file_path)

        write_Path_Table_Rules(p4info_helper, switches, paths, port_mapping)

        write_sw_config(p4info_helper, switches, switches_conected_to_client, switches_conected_to_server)

        write_weight_table_config(p4info_helper, switches)

        write_dnat_table_config(p4info_helper, switches, hosts_server_1, paths)

        #for sw in switches_conected_to_client:
        for s in switches:
            #if sw == s.name:
            write_ipv4_lpm_rules(p4info_helper, s)
            #break

        hosts_server_1 = [{"name": "h5"}, {"name": "h6"}]   #TODO

        #configure initial paths
        initial_paths = []
        for sw in switches_conected_to_client:
            for s in switches:
                if sw == s.name:
                    p = []
                    for h in hosts_server_1:
                        selected_paths = get_initial_paths(paths,s.name, h["name"])
                        p.append(selected_paths[0])
                        p.append(selected_paths[1])

                    print(f'{s.name} initial paths {p}')
                    initial_paths.append(f'{s.name} paths {p}')
                    sendPacketOut(p4info_helper, s, p)
                    break


        #readTableRules(p4info_helper, switches[3])

        # Create and start threads for PacketIn processing
        for sw in switches_conected_to_client:
            for s in switches:
                if sw == s.name:
                    t = threading.Thread(target=processPacketIn, args=(s,))
                    t.daemon = True  # makes the thread exit when main thread exits
                    t.start()
                    threads.append(t)


        # Thread to process received INT data
        t = threading.Thread(target=packetProcessor, args=())
        t.daemon = True
        t.start()
        threads.append(t)

        # Thread to interact with the RL agent
        t = threading.Thread(target=init_server, args=(p4info_helper, switches, paths))
        t.daemon = True
        t.start()
        threads.append(t)



        while True:
            sleep(2)
            print('\n----- p4controller -----')
            global current_paths
            print(f'Initial paths {initial_paths}')
            print(f'current_paths {current_paths}')


    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)
    finally:
        # Wait for threads to finish
        for t in threads:
            t.join(timeout=1)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':

    print('Init p4controller.py')

    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='../build/basic.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='../build/basic.json')
    parser.add_argument('--topo', help='Topology JSON file',
                        type=str, action="store", required=False,
                        default='../configs/fat-tree/topology.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    if not os.path.exists(args.topo):
        parser.print_help()
        print("\nTopology JSON file not found: %s\n" % args.topo)
        parser.exit(1)
    main(args.p4info, args.bmv2_json, args.topo)
