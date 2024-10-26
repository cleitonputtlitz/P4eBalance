#!/usr/bin/env python3
import os
import sys
import json
import yaml
import grpc
import time
# Import P4Runtime lib from parent utils dir
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.switch import ShutdownAllSwitchConnections
from p4runtime_lib.convert import encodeNum

def load_switches_conf():
    data = {}
    with open('../configs/switches.json', 'r') as json_file:
        data = yaml.safe_load(json_file)

    return data

def connect_to_switches(switches_config):
    # Create a switch connection object
    # this is backed by a P4Runtime gRPC connection.
    # Also, dump all P4Runtime messages sent to switch to given txt files.
    switches = []
    for switch in switches_config:
        switches.append(
            p4runtime_lib.bmv2.Bmv2SwitchConnection(
                name=switch["name"],
                address=switch["address"],
                device_id=switch["device_id"],
                proto_dump_file=switch["proto_dump_file"]))

    return switches

def send_master_arbitration_updates(switches):
    # Send master arbitration update message to establish this controller as
    # master (required by P4Runtime before performing any other write operation)
    for switch in switches:
        switch.MasterArbitrationUpdate()

def set_pipelines(switches, p4info_helper, bmv2_file_path):
    # Install the P4 program on the switches
    for switch in switches:
        switch.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                           bmv2_json_file_path=bmv2_file_path)

def write_Path_Table_Rules(p4info_helper, switches, all_paths, port_mapping):

    print("write_Path_Table_Rules init")
    #direction = 0 - ida
    for (switch, host), paths in all_paths.items():
        #print(switch, host)
        for path_info in paths:
            path = path_info[1]
            #print('configurando ', path_info)

            #if(int(path_info[0] > 10)):  #TODO
                #break

            #percorre cada salto do caminho
            for i in range(0, len(path) - 1):
                current_node = path[i]
                next_node = path[i + 1]
                #print('current_node ' + current_node)
                for sw_a in switches:   #TODO
                    if(sw_a.name == current_node):
                        sw = sw_a
                        break
                #print('sw.name ' + sw.name + ' int(path_info[0]) ', path_info[0])
                #time.sleep(3)
                if (current_node, next_node) in port_mapping:
                    port = port_mapping[(current_node, next_node)][1:]

                    table_entry = p4info_helper.buildTableEntry(
                        table_name="MyIngress.path_table",
                        match_fields={
                            "hdr.LB_path.path_id": int(path_info[0]),
                            "hdr.LB_path.direction": 0
                        },
                        action_name="MyIngress.set_LB_path",
                        action_params={
                            "port": int(port),
                            "lastHop": 0,
                            "direction": 0
                        })
                    #print(table_entry)
                    sw.WriteTableEntry(table_entry)

    #direction = 1 -volta
    print('gerando conf volta')
    for (switch, host), paths in all_paths.items():
        for path_info in paths:
            #if(int(path_info[0] > 10)):  #TODO
                #break
            path = path_info[1]
            #percorre cada salto do caminho
            for i in range(len(path) - 2, -1, -1):
                current_node = path[i]
                next_node = path[i - 1]

                for sw_a in switches:   #TODO
                    if(sw_a.name == current_node):
                        sw = sw_a
                        break

                if(i == 0):
                    lastHop = 1
                else:
                    lastHop = 0

                if (current_node, next_node) in port_mapping:
                    port = port_mapping[(current_node, next_node)][1:]
                    table_entry = p4info_helper.buildTableEntry(
                        table_name="MyIngress.path_table",
                        match_fields={
                            "hdr.LB_path.path_id": int(path_info[0]),
                            "hdr.LB_path.direction": 1
                        },
                        action_name="MyIngress.set_LB_path",
                        action_params={
                            "port": int(port),
                            "lastHop": lastHop,
                            "direction": 1
                        })
                    sw.WriteTableEntry(table_entry)
                if lastHop == 1:
                    port = 0
                    table_entry = p4info_helper.buildTableEntry(
                        table_name="MyIngress.path_table",
                        match_fields={
                            "hdr.LB_path.path_id": int(path_info[0]),
                            "hdr.LB_path.direction": 1
                        },
                        action_name="MyIngress.set_LB_path",
                        action_params={
                            "port": int(port),
                            "lastHop": lastHop,
                            "direction": 1
                        })
                    sw.WriteTableEntry(table_entry)

    print('write_Path_Table_Rules done')


def write_sw_config(p4info_helper, switches, switches_conected_to_client, switches_conected_to_server):
    print('write_sw_config init')
    for sw in switches:
        #check if the switch is connected to a client or a server
        sw_direction = 0
        if(sw.name in switches_conected_to_server):
            sw_direction = 1

        table_entry = p4info_helper.buildTableEntry(
            table_name="MyIngress.sw_config",
            #match_fields={
            #    "hdr.LB_path.path_id": int(path_info['id'])
            #},
            action_name="MyIngress.get_switch_config",
            action_params={
                "swid": int(sw.device_id),
                "freq_collect_INT": 0, #10000, #100us
                "sw_direction": sw_direction
            })
        sw.WriteTableEntry(table_entry)
    print('write_sw_config done')

def write_dnat_table_config(p4info_helper, switches, hosts_server_1, all_paths):
    print('write_dnat_table_config init')

    for (switch, host), paths in all_paths.items():
        print(switch, host)
        for path_info in paths:
            print(path_info)
            for h in hosts_server_1:
                if h["name"] == host:
                    dst_ip_addr = h["address"]
                    break
            print(dst_ip_addr)
            for sw in switches:
                if(sw.name == switch):
                    print(f'achou conf switch {sw.name}')
                    table_entry = p4info_helper.buildTableEntry(
                        table_name="MyIngress.dnat_table",
                        match_fields={
                            "hdr.ipv4.dstAddr": ("10.0.10.10", 32),
                            "hdr.LB_path.path_id": int(path_info[0])
                        },
                        action_name="MyIngress.change_dstAddr",
                        action_params={
                            "dstAddr": dst_ip_addr
                        })
                    sw.WriteTableEntry(table_entry)
                    break

    print('write_dnat_table_config done')

def write_weight_table_config(p4info_helper, switches):
    print('write_weight_table_config init')
    weights = ([25, 5], [50, 4], [70, 3], [90, 2], [100, 1])
    for sw in switches:
        for weight in weights:
            table_entry = p4info_helper.buildTableEntry(
                table_name="MyIngress.weight_table",
                match_fields={
                    "meta.current_path_weight": weight[0]
                },
                action_name="MyIngress.get_weight_config",
                action_params={
                    "weight": weight[1]
                })
            sw.WriteTableEntry(table_entry)
    print('write_weight_table_config done')

def write_ipv4_lpm_rules(p4info_helper, sw):

    json_file_path = f'../configs/fat-tree/{sw.name}-runtime.json'

    if (os.path.isfile(json_file_path)):
        #json_file_path = '../configs/pod-topo/s1-runtime.json'
        with open(json_file_path, 'r') as f:
            config = json.load(f)

        print('write_ipv4_lpm_rules init')

        for entry in config["table_entries"]:
            table_name = entry["table"]
            default_action = entry.get("default_action", False)
            action_name = entry["action_name"]
            action_params = entry.get("action_params", {})

            if default_action:
                table_entry = p4info_helper.buildTableEntry(
                    table_name=table_name,
                    default_action=default_action,
                    action_name=action_name,
                    action_params=action_params
                )
            else:
                match_fields = entry.get("match", {})
                table_entry = p4info_helper.buildTableEntry(
                    table_name=table_name,
                    match_fields=match_fields,
                    action_name=action_name,
                    action_params=action_params
                )
            sw.WriteTableEntry(table_entry)

    print('write_ipv4_lpm_rules done')

def readTableRules(p4info_helper, sw):
    """
    Reads the table entries from all tables on the switch.

    :param p4info_helper: the P4Info helper
    :param sw: the switch connection
    """
    print('\n----- Reading tables rules for %s -----' % sw.name)
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry
            # TODO For extra credit, you can use the p4info_helper to translate
            #      the IDs in the entry to names
            table_name = p4info_helper.get_tables_name(entry.table_id)
            print('%s: ' % table_name, end=' ')
            for m in entry.match:
                print(p4info_helper.get_match_field_name(table_name, m.field_id), end=' ')
                print('%r' % (p4info_helper.get_match_field_value(m),), end=' ')
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print('->', action_name, end=' ')
            for p in action.params:
                print(p4info_helper.get_action_param_name(action_name, p.param_id), end=' ')
                print('%r' % p.value, end=' ')
            print()

def printCounter(p4info_helper, sw, counter_name, index):
    """
    Reads the specified counter at the specified index from the switch. In our
    program, the index is the tunnel ID. If the index is 0, it will return all
    values from the counter.

    :param p4info_helper: the P4Info helper
    :param sw:  the switch connection
    :param counter_name: the name of the counter from the P4 program
    :param index: the counter index (in our case, the tunnel ID)
    """
    for response in sw.ReadCounters(p4info_helper.get_counters_id(counter_name), index):
        for entity in response.entities:
            counter = entity.counter_entry
            print("%s %s %d: %d packets (%d bytes)" % (
                sw.name, counter_name, index,
                counter.data.packet_count, counter.data.byte_count
            ))

def load_hosts_conf():
    data = {}
    with open('../configs/hosts.json', 'r') as json_file:
        data = yaml.safe_load(json_file)

    return data

def get_sw_host_type(switch, host, switch_host_map):
    if switch in switch_host_map:
        for h, host_type in switch_host_map[switch]:
            if(h == host or host == ''):
                return host_type
    return 0

def printGrpcError(e):
    print("gRPC Error:", e.details(), end=' ')
    status_code = e.code()
    print("(%s)" % status_code.name, end=' ')
    traceback = sys.exc_info()[2]
    print("[%s:%d]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))
