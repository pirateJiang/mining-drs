"""
Algorithm: PPO (Proximal Policy Optimization)
Mine Type: Fixed Mine
MDP Type: Event-based Semi-MDP
Action Space: Discrete

This file demonstrates how to train a PPO agent on the ExampleMineModel.
"""

from env import MineEnv

if __name__ == "__main__":
    from gymnasium.utils.env_checker import check_env

    # 1. Initialize the environment
    env = MineEnv()

    print("Checking environment with gymnasium env_checker...")
    check_env(env)
    print("Environment check passed!")

    print("\n[Placeholder] Initialize PPO agent here")
    # Example: model = PPO("MlpPolicy", env, verbose=1)
    # model.learn(total_timesteps=10000)

    print("\nRunning a random agent for 10 steps as a placeholder...")
    obs, info = env.reset()
    for i in range(10):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        print(
            f"Step {i+1} | Action: {env.allowed_modes[action].name} | Reward: {reward:.2f} | Mode: {info['current_mode']} | Time: {info['current_time']:.2f}"
        )
        if terminated or truncated:
            print("Episode finished early!")
            break
