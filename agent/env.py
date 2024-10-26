
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from itertools import combinations
import requests
from time import sleep

# URL do controlador
controller_url = 'http://localhost:5000'

#https://stable-baselines3.readthedocs.io/en/master/guide/custom_env.html

#Model-free reinforcement learning
#This approach focuses on learning directly from interaction with the environment without explicitly building an internal model

class LoadBalancingEnv(gym.Env):
    def __init__(self, num_switches, num_servers, num_paths, k):
        super(LoadBalancingEnv, self).__init__()

        # Parâmetros do ambiente
        self.num_switches = num_switches
        self.num_servers = num_servers
        self.num_paths = num_paths
        self.k = k
        self.rewards = []
        self.paths = self._get_paths('s1')

        self.action_map = self._gerar_acoes()   #combinacoes de acoes

        # Faixas dinâmicas para cada métrica
        self.deq_qdepth_min, self.deq_qdepth_max = float('inf'), float('-inf')
        self.deq_timedelta_min, self.deq_timedelta_max = float('inf'), float('-inf')
        self.qtd_drop_min, self.qtd_drop_max = float('inf'), float('-inf')
        self.cpu_occupancy_min, self.cpu_occupancy_max = float('inf'), float('-inf')

        #combinaçoes de rotas disponiveis
        # num_paths - numero de caminhos disponiveis
        # k - numero de rotas que o agente deve selecionar a cada açao
        self.C = int(np.math.factorial(num_paths) / (np.math.factorial(k) * np.math.factorial((num_paths - k))))
        print(f'combinaçoes de rotas disponiveis {self.C}')

        # Define the action space
        # MultiBinary: A list of possible actions, where each timestep any of the actions can be used in any combination
        self.action_space = spaces.Discrete(self.C)


        # Espaço de observação: vetor de métricas para cada switch e host
        # [deq_qdepth, deq_timedelta, qtd_drop] for each switch
        # [cpu_occupancy] for each end-host
        self.observation_space = spaces.Box(
            low=0,
            high=np.inf,
            shape=(self.num_switches * 3 + self.num_servers,),
            dtype=np.float32
        )

        # Estado inicial, um vetor de zeros com as mesmas dimensões do espaço de observação
        self.state = np.zeros(self.num_switches * 3 + self.num_servers, dtype=np.float32)

        self.reset(72)

    def reset(self, seed):
        # called at the beginning of an episode, it returns an observation
        self.state = np.zeros(self.num_switches * 3 + self.num_servers, dtype=np.float32)
        #Recuperar o estado do ambiente (metricas INT)
        return self.state

    def step(self, action):

        # called to take an action with the environment
        # it returns the next observation, the immediate reward, whether the episode is over and additional information

        #select an action
        paths = self.action_map[action]

        #apply the action to the data plane
        sw_id = 0   #TODO sw1
        self._install_paths(sw_id, paths)

        #wait time for the applied action to take effect
        sleep(5)    #TODO

        # Get new metrics
        new_metrics = self._get_metrics()

        # Atualizar os valores máximos e mínimos observados
        self._update_dynamic_ranges(new_metrics)

        # Normalizar as métricas com base nas faixas dinâmicas
        if(new_metrics):
            switch_metrics = new_metrics[:self.num_switches * 3]
            #'q_delay', 'q_depth', 'q_drops'
            deq_timedeltas = (switch_metrics[0::3] - self.deq_qdepth_min) / (self.deq_qdepth_max - self.deq_qdepth_min + 1e-5)
            #deq_qdepths = switch_metrics[1::3] #(switch_metrics[1::3] - self.deq_timedelta_min) / (self.deq_timedelta_max - self.deq_timedelta_min + 1e-5)
            deq_qdepths = (switch_metrics[1::3] - self.deq_timedelta_min) / (self.deq_timedelta_max - self.deq_timedelta_min + 1e-5)
            qtd_drops = (switch_metrics[2::3] - self.qtd_drop_min) / (self.qtd_drop_max - self.qtd_drop_min + 1e-5)
            #cpu_occupancies = new_metrics[-self.num_servers:] #(new_metrics[-self.num_servers:] - self.cpu_occupancy_min) / (self.cpu_occupancy_max - self.cpu_occupancy_min + 1e-5)
            cpu_occupancies = (new_metrics[-self.num_servers:] - self.cpu_occupancy_min) / (self.cpu_occupancy_max - self.cpu_occupancy_min + 1e-5)

            # Atualizar o estado
            self.state = np.concatenate([deq_qdepths, deq_timedeltas, qtd_drops, cpu_occupancies])
        else:
            self.state = np.zeros(self.num_switches * 3 + self.num_servers, dtype=np.float32)

        print('metricas')
        #print(deq_qdepths)
        #print(deq_timedeltas)
        # Calcula a recompensa da açao tomada: inversa da maior utilização da fila
        # deq_qdepths = self.state[0::3]

        # pior de todos
        #deq_qdepth_max = np.max(deq_qdepths) if np.max(deq_qdepths) > 0 else 0.1
        #cpu_occupancy_max = np.max(cpu_occupancies) if np.max(cpu_occupancies) > 0 else 1

        # melhor desempenho
        deq_qdepth_max = np.std(deq_qdepths)    if np.std(deq_qdepths) > 0 else 0.1
        cpu_occupancy_max = np.std(cpu_occupancies) if np.std(cpu_occupancies) > 0 else 0.1

        # segundo melhor
        #deq_qdepth_max = np.mean(deq_qdepths)    if np.mean(deq_qdepths) > 0 else 0.1
        #cpu_occupancy_max = np.mean(cpu_occupancies) if np.mean(cpu_occupancies) > 0 else 0.1

        print(f'max deq_qdepth {deq_qdepth_max} cpu_occupancy_max {cpu_occupancy_max}')

        # ***************** Calcular a recompensa ******************************
        #reward = Betha1 * (1/(max(deq_qdepth))) + Betha2 * (1/(max(cpu)))
        #Betha1 and Betha2 are tunable parameters for providing a weight value for a specific metric

        # Teste 1: 100% rede, 0% HOST
        #Betha1 = 1.0
        #Betha2 = 0

        # ******** Teste 2: 50% rede, 50% HOST
        #Betha1 = 0.5
        #Betha2 = 0.5

        # ******** Teste 3: 80% rede, 20% HOST
        #Betha1 = 0.8
        #Betha2 = 0.2

        # ******* Teste 4: 20% rede, 80% HOST
        Betha1 = 0.2
        Betha2 = 0.8

        reward = Betha1 * (1 / deq_qdepth_max) + Betha2 * (1 / cpu_occupancy_max)


        self.rewards.append(reward)
        if len(self.rewards) > 10:
            self.rewards.pop(0)

        # Definir se o episódio terminou
        '''
        if len(self.rewards) == 10 and abs(self.rewards[-1] - self.rewards[-10]) < 0.01:
            done = True
        else:
            done = False
        '''
        reward_mean = np.mean(self.rewards)
        reward_std_dev = np.std(self.rewards)


        '''
        if len(self.rewards) == 10 and reward_std_dev < 0.000001:
            done = True
            print(f'reward_mean {reward_mean} reward_std_dev {reward_std_dev}')
        else:
            done = False
        '''
        done = False

        info = {f'selected {paths} paths'}

        return self.state, reward, done, info

    #  Get metrics from controller
    def _get_metrics(self):
        response = requests.get(f'{controller_url}/get_metrics')
        metrics=[]
        if response.status_code == 200:
            data = response.json()
            # Recuperar os dicionários de métricas de switches e hosts
            switch_metrics = data.get('switch_metrics', {})
            host_metrics = data.get('host_metrics', {})

            if isinstance(switch_metrics, dict):
                for switch_id, metrics_dict in switch_metrics.items():
                    # Adicionar os valores de cada métrica dos switches ao vetor de métricas
                    metrics.extend(metrics_dict.values())
            else:
                print('Unexpected format for switch_metrics')

            # Processar as métricas dos hosts
            if isinstance(host_metrics, dict):
                for host_id, metrics_dict in host_metrics.items():
                    # Adicionar os valores de cada métrica dos hosts ao vetor de métricas
                    metrics.extend(metrics_dict.values())
            else:
                print('Unexpected format for host_metrics')

        else:
            print('Error fetching metrics')

        print('get_metrics')
        print(metrics)
        return metrics

    def _update_dynamic_ranges(self, new_metrics):
        # Atualizando faixas mínimas e máximas dinamicamente

        if(not new_metrics):
            return
        switch_metrics = new_metrics[:self.num_switches * 3]
        self.deq_qdepth_min = min(self.deq_qdepth_min, np.min(switch_metrics[0::3]))
        self.deq_qdepth_max = max(self.deq_qdepth_max, np.max(switch_metrics[0::3]))
        self.deq_timedelta_min = min(self.deq_timedelta_min, np.min(switch_metrics[1::3]))
        self.deq_timedelta_max = max(self.deq_timedelta_max, np.max(switch_metrics[1::3]))
        self.qtd_drop_min = min(self.qtd_drop_min, np.min(switch_metrics[2::3]))
        self.qtd_drop_max = max(self.qtd_drop_max, np.max(switch_metrics[2::3]))
        self.cpu_occupancy_min = min(self.cpu_occupancy_min, np.min(new_metrics[-self.num_servers:]))
        self.cpu_occupancy_max = max(self.cpu_occupancy_max, np.max(new_metrics[-self.num_servers:]))


    # get all paths
    def _get_paths(self, source):

        hosts = ["h5", "h6"]   #TODO

        params = {
            'source': source,
            'dest': ','.join(hosts)  # Join the list into a comma-separated string
        }

        response = requests.get(f'{controller_url}/get_paths', params=params)
        if response.status_code == 200:
            data = response.json()
            paths = data['paths']
            print('_get_paths:', paths)
        else:
            print('Error fetching paths', response.status_code)
            paths = []

        return paths

    # Sends the selected paths to the controller to install
    def _install_paths(self, sw_id, paths):
        response = requests.post(f'{controller_url}/install_paths', json={'sw_id':sw_id, 'paths': paths})
        if response.status_code == 200:
            return 'Install confirmation:', response.json()
        else:
            return 'Error installing paths:', response.status_code

    def _gerar_acoes(self):
        # Gerar todas as combinações possíveis de num_rotas_selecionadas a partir de rotas_disponiveis
        combinacoes = list(combinations(self.paths, self.k))

        acoes = [list(combo) for combo in combinacoes]

        return acoes
