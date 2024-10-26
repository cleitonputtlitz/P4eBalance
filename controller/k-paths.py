import networkx as nx

def find_all_paths_multiple_targets(graph, source, targets):
    # Lista para armazenar todos os caminhos de source para cada destino em targets
    all_paths = []

    # Para cada target, encontrar todos os caminhos do source até o target
    for target in targets:
        all_paths += list(nx.all_simple_paths(graph, source, target))

    return all_paths

def calculate_penalty_complete(path, selected_paths):
    # Penalização para caminhos que compartilhem switches ou hosts com caminhos já selecionados
    penalty = 0
    nodes_in_selected_paths = set()

    for selected_path in selected_paths:
        nodes_in_selected_paths.update(selected_path)

    # Aplica penalização para cada nó que já aparece nos caminhos selecionados
    for node in path:
        if node in nodes_in_selected_paths:
            penalty += 1

    return penalty

def k_best_paths_with_penalty_complete(graph, source, targets, k):
    # Encontra todos os caminhos entre source e todos os targets
    all_paths = find_all_paths_multiple_targets(graph, source, targets)

    # Inicializa os caminhos selecionados e a lista de caminhos com pontuação
    scored_paths = []
    selected_paths = []

    for path in all_paths:
        # O comprimento do caminho é sua pontuação inicial (quanto menor, melhor)
        score = len(path)
        # Calcula a penalização baseada em switches e hosts compartilhados
        penalty = calculate_penalty_complete(path, selected_paths)
        total_score = score + penalty
        scored_paths.append((path, total_score))

    # Ordena os caminhos por pontuação total (incluindo penalização)
    scored_paths.sort(key=lambda x: x[1])

    # Seleciona os k melhores caminhos com menor pontuação
    selected_paths = [path for path, score in scored_paths[:k]]

    return selected_paths

# Topologia de exemplo
edges = [
    ("h1", "s1"), ("h2", "s1"),
    ("h3", "s2"), ("h4", "s2"),
    ("h5", "s3"), ("h6", "s3"),
    ("h7", "s4"), ("h8", "s4"),
    ("s1", "s5"), ("s1", "s6"),
    ("s2", "s5"), ("s2", "s6"),
    ("s3", "s7"), ("s3", "s8"),
    ("s4", "s7"), ("s4", "s8"),
    ("s5", "s9"), ("s5", "s10"),
    ("s6", "s9"), ("s6", "s10"),
    ("s7", "s10"), ("s7", "s9"),
    ("s8", "s10"), ("s8", "s9")
]

# Cria o grafo
G = nx.Graph()
for u, v in edges:
    G.add_edge(u, v, weight=1)  # Pesos iguais (latência e largura de banda)

# Encontra os 10 melhores caminhos de s1 para os hosts ['h5', 'h6', 'h7', 'h8']
source = 's2'
targets = ['h5', 'h6']
k = 20
best_paths = k_best_paths_with_penalty_complete(G, source, targets, k)

# Imprime os melhores caminhos
print("Melhores Caminhos:")
for i, path in enumerate(best_paths):
    print(f"Caminho {i+1}: {path}")
