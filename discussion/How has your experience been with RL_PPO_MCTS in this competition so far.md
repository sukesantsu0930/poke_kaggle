How has your experience been with RL/PPO/MCTS in this competition so far?
Hi everyone,

With the competition in full swing and some extremely strong heuristic baselines dominating the top spots on the leaderboard (as far as visible on public notebooks), I wanted to open a thread to discuss how people are approaching machine learning methods—specifically Reinforcement Learning (PPO, DQN) and Monte Carlo Tree Search (MCTS).

Since the simulation engine (libcg.so) is a closed-source C++ binary, we are bound to sequential CPU environments rather than massive JAX/TPU vectorization. I’ve been building an offline training pipeline and wanted to share my initial experience and ask how others are tackling these engineering bottlenecks:

1. Handling Memory Leaks & Emulation
Since many of us are developing on macOS (Apple Silicon), we've been running simulation playouts inside an emulated linux/amd64 Docker container. The simulator has some noticeable C++ memory leakage over long runs, so we implemented process-level isolation (restarting worker threads every 25-50 matches) to keep the OS memory clean during self-play rollout generation.

2. Supervised Bootstrapping (Behavioral Cloning)
To avoid the agent wasting millions of steps exploring randomly in a complex, imperfect-information card game, we pre-trained a state-transformer policy/value network (MyModel) to mimic the top Lucario heuristic pilot.

Validation Accuracy: Converged to around 66% accuracy in predicting the exact card combination choices.
Direct Win Rate: Playing greedily (no search), the BC agent achieved a 10% win rate against the heuristic baseline.
3. Self-Play RL (PPO) Fine-Tuning
We ran a 20-iteration self-play PPO loop, mixing 50% self-play matches and 50% matches against the Heuristic Agent (league training). To prevent policy collapse and catastrophic forgetting of the heuristic prior, we added a Kullback-Leibler (KL) divergence penalty between the active RL policy and the frozen BC prior.

Results: The policy optimization was very stable (KL divergence held around 0.01 - 0.09), and the raw policy network win rate against the Heuristic Agent peaked at 25.0% (without search lookahead).
4. The MCTS Bottleneck
The Kaggle worker environment imposes a strict 1-second move timeout. In our MCTS rollout tests, this limits the search budget to roughly 10 rollouts per turn. At this extremely low budget, standard UCT search is practically useless because it wastes rollouts exploring random branches. We are using our trained RL policy as a prior probability distribution ($P(s, a)$ in PUCT) to focus all 10 rollouts on the top-2 or top-3 candidate moves.

I would love to hear from other teams:

RL vs. Heuristics: Has anyone successfully trained a pure or hybrid RL model that consistently beats the 1091-scoring heuristic baselines offline?
Action Masking: How are you representing candidate action combinations in the policy decoder given the dynamic size of legal action sets? Are you using autoregressive selection or fixed combinations?
MCTS Value: Are you finding search helpful under the 1-second timeout, or is the agent relying almost entirely on the neural network's prior?
Good luck to everyone on the leaderboard!