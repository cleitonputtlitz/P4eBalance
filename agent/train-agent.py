
import numpy as np
import gym
import random
from env import LoadBalancingEnv
from agent import DQNAgent

# Instantiate the env
env = LoadBalancingEnv(num_switches=10, num_servers=2, num_paths=12, k=4)
#24 caminhos entre s1 com destino para h5 e h6. Selecionar 4 melhores.

# DQN agent
state_size = env.observation_space.shape[0]
action_size = env.action_space.n

agent = DQNAgent(state_size, action_size)

# Deep Q-Learning Algorithm

state = env.reset(72)   # Reset the environment
#rewards = []
step = 0
output_file_data = []
output_file_data.append('Step; Reward')

#for step in range(10):
try:
    while True:

        step += 1

        # Choose an action
        action = agent.act(state)

        # take action and observe reward
        next_state, reward, done, info = env.step(action)

        agent.remember(state, action, reward, next_state, done)

        #Update new state
        state = next_state
        agent.replay()

        #rewards.append(reward)
        print("Step {}".format(step), "action ", action, "reward ", reward, "paths ", info)

        output_data_line = '{0}; {1}'.format(step, reward)
        output_file_data.append(output_data_line)

        if done or step > 690:
            print("Finished after {} timesteps".format(step))
            break

except Exception as e:
    print(f"Exception: {e}")
finally:
    with open('train_agent.csv', 'w+') as output_file:
        for item in output_file_data:
            output_file.write("%s\n" % item)
