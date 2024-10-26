import random
from collections import deque

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

class QNetwork(nn.Module):
    def __init__(self, state_size, action_size, hidden_size=64):
        super(QNetwork, self).__init__()
        self.fc1 = nn.Linear(state_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.fc3 = nn.Linear(hidden_size, action_size)

    def forward(self, state):
        x = torch.relu(self.fc1(state))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)

class DQNAgent:                                             #lr=0.05
    def __init__(self, state_size, action_size, gamma=0.95, lr=0.1, batch_size=8, memory_size=10000):  #TODO batch_size
        #gamma=0.99, lr=0.001,
        self.state_size = state_size
        self.action_size = action_size
        self.gamma = gamma  # Fator de desconto
        self.lr = lr  # Taxa de aprendizado
        self.batch_size = batch_size
        self.memory = deque(maxlen=memory_size)
        self.epsilon = 1.0  # Taxa de exploração (começa com exploração total)
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.95

        # Inicializar a rede neural Q e o otimizador
        self.q_network = QNetwork(state_size, action_size)
        self.optimizer = optim.Adam(self.q_network.parameters(), lr=self.lr)
        self.loss_fn = nn.MSELoss()

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state):
        # Escolha uma ação de acordo com a política epsilon-greedy
        if np.random.rand() <= self.epsilon:
            return random.choice(range(self.action_size))

        state = torch.FloatTensor(state).unsqueeze(0)
        q_values = self.q_network(state)
        return np.argmax(q_values.detach().numpy())

    def replay(self):
        # Só treina se a memória tem um lote completo
        if len(self.memory) < self.batch_size:
            return

        # Amostra de minibatch de transições
        minibatch = random.sample(self.memory, self.batch_size)

        for state, action, reward, next_state, done in minibatch:
            state = torch.FloatTensor(state).unsqueeze(0)
            next_state = torch.FloatTensor(next_state).unsqueeze(0)
            target = reward
            if not done:
                target = reward + self.gamma * torch.max(self.q_network(next_state)).item()

            q_values = self.q_network(state)
            target_f = q_values.clone()
            target_f[0][action] = target

            # Calcular perda e backpropagation
            loss = self.loss_fn(q_values, target_f)
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

        # Decair o valor de epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def load(self, name):
        self.q_network.load_state_dict(torch.load(name))

    def save(self, name):
        torch.save(self.q_network.state_dict(), name)
