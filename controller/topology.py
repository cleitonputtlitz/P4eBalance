import json
import yaml
from collections import defaultdict
from ksp import find_k_shortest_paths, build_graph_ksp

path_id = 1

def load_topology(json_file):
    with open(json_file, 'r') as file:
        topology = json.load(file)
    return topology

def load_hosts_conf(file_name):
    data = {}
    with open(file_name, 'r') as json_file:
        data = yaml.safe_load(json_file)

    return data

# Função para capturar os hosts, switches e links
def parse_topology(topology):
    hosts = topology.get("hosts", {})
    switches = topology.get("switches", {})
    links = topology.get("links", [])

    return hosts, switches, links

def map_switch_host_types(topology, host_info):

    host_type_mapping = {host["name"]: host["server"] for host in host_info["hosts"]}

    # Dictionary to store switch connections and host types
    switch_host_type_map = {}

    # Iterate over links to map switch to host and host type
    for link in topology["links"]:
        host, switch_port = link

        # Extract the switch name from the port (e.g., "s1-p1" -> "s1")
        switch = switch_port.split('-')[0]

        # Check if the current link connects a host
        if host in topology["hosts"]:
            # Get the type of the host
            host_type = host_type_mapping.get(host)

            if switch not in switch_host_type_map:
                switch_host_type_map[switch] = []

            # Add the host and its type to the switch map
            switch_host_type_map[switch].append((host, host_type))

    return switch_host_type_map

def generate_switch_config(switches):
    sw_data = {"switches":[]}
    data = sw_data["switches"]
    device_id = 0
    port = 50051
    for sw in switches:
        data.append({'name':sw,
                     'address':f"127.0.0.1:{port}",
                    'device_id':device_id,
                    'proto_dump_file':f"../logs/{sw}-p4runtime-requests.txt"})
        device_id += 1
        port += 1

    file_path ='../configs/switches.json'
    with open(file_path, 'w') as outfile:
        json.dump(sw_data, outfile, indent=4)
    outfile.close()
    print('generate configs/switches.json')

# Função para construir o grafo da topologia
def build_graph(links):
    graph = defaultdict(list)
    port_mapping = {}
    for link in links:

        src, dst = link[0], link[1]
        src_node = src.split('-')[0]  # Obtém o nome do switch sem a porta
        dst_node = dst.split('-')[0]  # Obtém o nome do switch sem a porta
        src_port = src.split('-')[1] if '-' in src else None
        dst_port = dst.split('-')[1] if '-' in dst else None

        graph[src_node].append(dst_node)
        graph[dst_node].append(src_node)

        if src_port:
            port_mapping[(src_node, dst_node)] = src_port
        if dst_port:
            port_mapping[(dst_node, src_node)] = dst_port

    return graph, port_mapping

# Função para encontrar todos os caminhos entre dois nós usando DFS
def find_all_paths(graph, start, end, path=[]):
    path = path + [start]
    if start == end:
        return [path]
    if start not in graph:
        return []
    paths = []
    for node in graph[start]:
        if node not in path:
            new_paths = find_all_paths(graph, node, end, path)
            for p in new_paths:
                paths.append(p)
    return paths

# Função para encontrar todos os caminhos possíveis entre todos os hosts
def find_paths_between_hosts(hosts, switches, graph):
    host_names = list(hosts.keys())
    paths = {}
    path_id = 1
    for i in range(len(host_names)):
        for j in range(i + 1, len(host_names)):
            host1 = host_names[i]
            host2 = host_names[j]
            paths_between = find_all_paths(graph, host1, host2)
            filtered_paths = [
                #{"id": f"path-{path_id + idx}", "path": path}
                {"id": f"{path_id + idx}", "path": path}
                for idx, path in enumerate(paths_between)
                if path[0] in hosts and path[-1] in hosts and any(s in path for s in switches)
            ]
            path_id += len(filtered_paths)
            paths[(host1, host2)] = filtered_paths

    print('find paths between hosts done')
    return paths

def switches_config(topology, host_info):
    # Create a mapping for host to server type
    host_type_mapping = {host["name"]: host["server"] for host in host_info["hosts"]}

    # Set to store switches connected to at least one host with server 0
    switches_conected_to_client = set()
    switches_conected_to_server = set()

    # Iterate over links to find relevant switches
    for link in topology["links"]:
        host, switch_port = link[0], link[1]

        # Extract the switch name from the port (e.g., "s1-p1" -> "s1")
        switch = switch_port.split('-')[0]

        # Check if the current link connects to a host and if it is server 0
        if host in topology["hosts"] and host_type_mapping.get(host) == 0:
            switches_conected_to_client.add(switch)

        if host in topology["hosts"] and host_type_mapping.get(host) == 1:
            switches_conected_to_server.add(switch)

    return switches_conected_to_client, switches_conected_to_server

def find_hosts_with_server_one(host_info):
    # List to store hosts with server 1
    hosts_with_server_one = [host["name"] for host in host_info["hosts"] if host["server"] == 1]
    return hosts_with_server_one

def find_paths_between_nodes(start, goal, graph):
    # Use BFS to find all paths from start to goal
    def bfs_paths(start, goal):
        queue = [(start, [start])]
        global path_id
        while queue:
            (vertex, path) = queue.pop(0)
            for next in set(graph[vertex]) - set(path):
                if next == goal:
                    yield (path_id, path + [next])
                    path_id += 1
                else:
                    queue.append((next, path + [next]))

    return list(bfs_paths(start, goal))

# Função para imprimir os caminhos gerados para cada par de origem e destino
def print_paths(paths):
    for host_pair, paths_list in paths.items():
        print(f"Caminhos entre {host_pair[0]} e {host_pair[1]}:")
        for path_info in paths_list:
            print(f"  ID: {path_info['id']}: {' -> '.join(path_info['path'])}")
        print()  # Linha em branco para separar os diferentes pares de hosts

def save_paths(all_paths):
    path_data = {"paths":[]}
    data = path_data["paths"]

    for (switch, host), paths in all_paths.items():
        for path_info in paths:
            data.append({'path-id':path_info[0],
                         'src': switch,
                         'dst': host,
                         'hops': ' -> '.join(path_info[1])
                        })

    file_path ='../configs/paths.json'
    with open(file_path, 'w') as outfile:
        json.dump(path_data, outfile, indent=4)
    outfile.close()
    print('generate configs/paths.json')

def topology_init(topo_file):

    topology = load_topology(topo_file)
    hosts, switches, links = parse_topology(topology)

    generate_switch_config(switches)

    host_config = load_hosts_conf('../configs/hosts.json')

    # Construir o grafo da topologia e mapeamento de portas
    graph, port_mapping = build_graph(links)
    #print('GRAPH ', graph)

    #TODO
    #graph2, _ = build_graph_ksp(links)

    # Encontrar todos os caminhos possíveis entre os hosts
    #paths = find_paths_between_hosts(hosts, switches, graph)
    #print_paths(paths)


    # Step 1: Find switches with at least one host of server type 0
    switches_conected_to_client, switches_conected_to_server = switches_config(topology, host_config)
    print("Switches connected to hosts with server = 0:", switches_conected_to_client)
    print("Switches connected to hosts with server = 1:", switches_conected_to_server)

    # Step 2: Find all hosts with server type 1
    hosts_with_server_one = find_hosts_with_server_one(host_config)
    print("Hosts with server = 1:", hosts_with_server_one)

    # Step 3: Find all paths between each switch with server=0 hosts and each host with server=1
    all_paths = {}
    for switch in switches_conected_to_client:
        #print('procurando caminhos do switch ',switch)
        for host in hosts_with_server_one:
            #paths = find_paths_between_nodes(switch, host, graph)
            paths = find_k_shortest_paths(source=switch, target=host, K=6)  #TODO TAVA 6
            print(paths)
            if paths:
                all_paths[(switch, host)] = paths

    #print("All paths between switches with server=0 hosts and hosts with server=1:")
    #for (switch, host), paths in all_paths.items():
    #    print(f"Paths between {switch} and {host}: {paths}")

    save_paths(all_paths)


    return all_paths, port_mapping, switches_conected_to_client, switches_conected_to_server


if __name__ == '__main__':
    topology_init()
