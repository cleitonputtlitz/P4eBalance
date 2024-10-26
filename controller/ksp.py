import json
import heapq
from copy import deepcopy
from collections import defaultdict

path_id = 1

g = {
    "s1": {"s5": 1, "s6": 1},
    "s2": {"s5": 1, "s6": 1},
    "s5": {"s9": 1, "s10": 1},
    "s6": {"s9": 1, "s10": 1},
    "s9": {"s7": 1, "s8": 1},
    "s10": {"s7": 1, "s8": 1},
    "s7": {"s3": 1, "s4": 1},
    "s8": {"s3": 1, "s4": 1},
    "s3": {"h5": 1, "h6": 1},
    "s4": {"h7": 1, "h8": 1},
    "h5": {},
    "h6": {},
    "h7": {},
    "h8": {}
}
'''
graph = {
    "s1": {"s2": 1, "s3": 1},
    "s2": {"s3": 1, "s10": 1},
    "s3": {"s10": 1},
    "s10": {}
}
'''
K = 6
source = "s1"
target = "h8"

def weight_func(edge):
    return graph[edge["fromNode"]][edge["toNode"]]

def ksp(graph, source, target, K, weight_func=None, edge_func=None):
    # Clonar o grafo para evitar alterações no original
    _g = deepcopy(graph)

    # Inicializar containers para caminhos candidatos e k caminhos mais curtos
    ksp = []
    candidates = []

    # Calcular e adicionar o caminho mais curto
    kth_path = get_dijkstra(_g, source, target, weight_func, edge_func)
    if not kth_path:
        return ksp
    ksp.append(kth_path)

    # Iterativamente calcular os k caminhos mais curtos
    for k in range(1, K):
        previous_path = deepcopy(ksp[k - 1])

        if not previous_path:
            break

        for i in range(len(previous_path["edges"])):
            removed_edges = []

            spur_node = previous_path["edges"][i]["fromNode"]
            root_path = clone_path_to(previous_path, i)

            for p in ksp:
                p = deepcopy(p)
                stub = clone_path_to(p, i)

                if is_path_equal(root_path, stub):
                    re = p["edges"][i]
                    _g[re["fromNode"]].pop(re["toNode"], None)
                    removed_edges.append(re)

            for root_path_edge in root_path["edges"]:
                rn = root_path_edge["fromNode"]
                if rn != spur_node:
                    removed_edges.extend(remove_node(_g, rn, weight_func))

            spur_path = get_dijkstra(_g, spur_node, target, weight_func, edge_func)

            if spur_path is not None:
                total_path = deepcopy(root_path)
                edges_to_add = deepcopy(spur_path["edges"])
                total_path["edges"].extend(edges_to_add)
                total_path["totalCost"] += spur_path["totalCost"]

                if not is_path_exist_in_array(candidates, total_path):
                    candidates.append(total_path)

            add_edges(_g, removed_edges)

        is_new_path = False
        while not is_new_path:
            kth_path = remove_best_candidate(candidates)
            if kth_path is not None:
                is_new_path = all(not is_path_equal(p, kth_path) for p in ksp)

        if kth_path is None:
            break

        ksp.append(kth_path)

    return ksp


def get_dijkstra(graph, source, target, weight_func=None, edge_func=None):
    if not weight_func:
        weight_func = lambda e: graph[e["fromNode"]][e["toNode"]]

    dijkstra = dijkstra_algorithm(graph, source, weight_func)
    return extract_path_from_dijkstra(graph, dijkstra, source, target, weight_func, edge_func)


def dijkstra_algorithm(graph, source, weight_func):
    distances = {node: float('inf') for node in graph}
    distances[source] = 0
    predecessors = {node: None for node in graph}

    queue = [(0, source)]
    while queue:
        current_distance, current_node = heapq.heappop(queue)

        if current_distance > distances[current_node]:
            continue

        for neighbor, weight in graph[current_node].items():
            distance = current_distance + weight_func({"fromNode": current_node, "toNode": neighbor})
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                predecessors[neighbor] = current_node
                heapq.heappush(queue, (distance, neighbor))

    return {"distances": distances, "predecessors": predecessors}


def extract_path_from_dijkstra(graph, dijkstra, source, target, weight_func=None, edge_func=None):
    if dijkstra["distances"][target] == float('inf'):
        return None

    edges = []
    current_node = target
    while current_node != source:
        previous_node = dijkstra["predecessors"][current_node]

        weight_value = weight_func({"fromNode": previous_node, "toNode": current_node}) if weight_func else graph[previous_node][current_node]
        edge = {"fromNode": previous_node, "toNode": current_node, "weight": weight_value}
        edges.append(edge)

        current_node = previous_node

    return {"totalCost": dijkstra["distances"][target], "edges": list(reversed(edges))}


def add_edges(graph, edges):
    for e in edges:
        graph.setdefault(e["fromNode"], {})[e["toNode"]] = e["weight"]


def remove_node(graph, node, weight_func=None):
    rem_edges = []
    for neighbor in list(graph.get(node, {})):
        weight_value = weight_func({"fromNode": node, "toNode": neighbor}) if weight_func else graph[node][neighbor]
        rem_edges.append({"fromNode": node, "toNode": neighbor, "weight": weight_value})

    graph.pop(node, None)
    return rem_edges


def clone_path_to(path, i):
    new_path = deepcopy(path)
    new_path["edges"] = new_path["edges"][:i]
    new_path["totalCost"] = sum(edge["weight"] for edge in new_path["edges"])
    return new_path


def is_path_equal(path1, path2):
    if not path2:
        return False

    return path1["edges"] == path2["edges"]


def is_path_exist_in_array(candidates, path):
    return any(is_path_equal(c, path) for c in candidates)


def remove_best_candidate(candidates):
    candidates.sort(key=lambda p: p["totalCost"])
    return candidates.pop(0) if candidates else None

def build_graph_ksp(links):
    graph = defaultdict(dict)
    port_mapping = {}

    # Atribuir um peso arbitrário a cada link (pode ser baseado em métricas de rede)
    default_weight = 1

    for link in links:
        src, dst = link[0], link[1]
        src_node = src.split('-')[0]  # Obtém o nome do switch sem a porta
        dst_node = dst.split('-')[0]  # Obtém o nome do switch sem a porta
        src_port = src.split('-')[1] if '-' in src else None
        dst_port = dst.split('-')[1] if '-' in dst else None

        # Adiciona uma aresta bidirecional com o peso padrão
        graph[src_node][dst_node] = default_weight
        graph[dst_node][src_node] = default_weight

        if src_port:
            port_mapping[(src_node, dst_node)] = src_port
        if dst_port:
            port_mapping[(dst_node, src_node)] = dst_port

    return graph, port_mapping

def extract_path_from_json(json_data):
    # Inicializa a lista com o nó de origem do primeiro edge
    path = [json_data["edges"][0]["fromNode"]]

    # Itera sobre as arestas, adicionando o nó de destino à lista de caminho
    for edge in json_data["edges"]:
        path.append(edge["toNode"])

    return path

def find_k_shortest_paths(source, target, graph=g,  K=3):

    global path_id
    paths_with_ids = []

    paths = ksp(graph, source, target, K)

    for i in range(K):
        path = extract_path_from_json(paths[i])
        paths_with_ids.append((path_id, path))
        path_id += 1

    return paths_with_ids
