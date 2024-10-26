# controller.py
from flask import Flask, jsonify, request
from engine_INT import switch_metrics, host_metrics
from p4controller import sendPacketOut

app = Flask(__name__)

global p4info_helper
global switches
global paths

# Função get_metrics que retorna as métricas
@app.route('/get_metrics', methods=['GET'])
def get_metrics():
    return jsonify({
        'switch_metrics': switch_metrics,
        'host_metrics': host_metrics
    })

# Função get_paths que retorna as rotas iniciais
@app.route('/get_paths', methods=['GET'])
def get_paths():
    source = request.args.get('source')
    dest = request.args.get('dest')

    print('get paths', dest)

    if source is None:
        return jsonify({'error': 'Parâmetro "source" é obrigatório'}), 400

    filtered_paths = []

    if dest is None:
        filtered_paths = [
            item[0] for (src, dest), sublist in paths.items() if src == source for item in sublist
        ]
    else:
        dest_list = [d.strip() for d in dest.split(',')]

        filtered_paths = [
            item[0] for (src, dest), sublist in paths.items() if src == source and dest in dest_list for item in sublist
        ]

    return jsonify({
        'paths': filtered_paths
        #'paths': [item[0] for sublist in paths.values() for item in sublist]
    })

# Função install_paths que recebe os ids dos caminhos e confirma instalação
@app.route('/install_paths', methods=['POST'])
def install_paths():
    global p4info_helper
    global switches

    paths = request.json.get('paths')
    sw = request.json.get('sw_id')

    sendPacketOut(p4info_helper, switches[sw], paths)

    return jsonify({'status': 'success', 'installed_paths': paths})


def init_server(p4info_helper_a, switches_a, paths_a):
    global p4info_helper
    global switches
    global paths

    p4info_helper = p4info_helper_a
    switches = switches_a
    paths = paths_a

    print('init controller server')
    app.run(host='0.0.0.0', port=5000)  # O servidor vai rodar na porta 5000
