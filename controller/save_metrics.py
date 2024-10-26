import time
import json
import redis

# Conectar ao servidor Redis
r = redis.StrictRedis(host='localhost', port=6379, db=0)

def send_metrics(switch_metrics, host_metrics):

    # Estrutura de dados a ser enviada
    data = {
        'switch_metrics': switch_metrics,
        'host_metrics': host_metrics
    }

    # Publica as métricas no Redis
    r.set('network_metrics', json.dumps(data))
    print("Controlador: Métricas processadas e enviadas para o Redis.")
