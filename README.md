# P4eBalance

### Start Mininet
```bash
make

```
### Start the controller in a different terminal
```bash
cd controller
python3 p4controller.py
```
### Start the RL agent in a different terminal
```bash
cd agent
python3 train-agent.py
```
### Generate traffic (in Mininet)
```bash
source run.sh
```
