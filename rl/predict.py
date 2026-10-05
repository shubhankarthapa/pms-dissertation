"""Run a trained DQN policy through one CI/CD metrics episode."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import numpy as np
from stable_baselines3 import DQN

if __package__:
    from .environment import CICDPipelineEnv, PipelineAction
else:
    from environment import CICDPipelineEnv, PipelineAction


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS_PATH = PROJECT_ROOT / "metrics_traditional.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "rl_model.zip"
ACTION_NAMES = {
    PipelineAction.STANDARD: "Standard Pipeline",
    PipelineAction.CACHE: "Enable Cache",
    PipelineAction.PARALLEL_TESTS: "Parallel Testing",
    PipelineAction.CACHE_AND_PARALLEL_TESTS: "Cache + Parallel Testing",
    PipelineAction.SECURITY_SCAN: "Security Scan",
    PipelineAction.FAST_BUILD: "Fast Build Mode",
    PipelineAction.RESOURCE_OPTIMIZED: "Resource Optimized Mode",
}
STATE_NAMES = (
    "build_time",
    "test_time",
    "deploy_time",
    "cpu_usage",
    "memory_usage",
    "success",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_METRICS_PATH,
        help="Path to metrics_traditional.csv",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Path to the trained DQN model (default: rl_model.zip)",
    )
    parser.add_argument(
        "--recommendation-file",
        type=Path,
        help="Write one selected action to this file instead of running a full episode",
    )
    parser.add_argument("--seed", type=int, default=42, help="Environment random seed")
    return parser.parse_args(argv)


def format_state(observation: np.ndarray) -> str:
    state = ", ".join(
        f"{name}={float(value):g}"
        for name, value in zip(STATE_NAMES, observation, strict=True)
    )
    return f"[{state}]"


def validate_model(model: DQN, env: CICDPipelineEnv) -> None:
    if model.observation_space.shape != env.observation_space.shape:
        raise ValueError(
            "Model observation shape "
            f"{model.observation_space.shape} does not match environment "
            f"shape {env.observation_space.shape}; retrain the model."
        )
    if model.action_space != env.action_space:
        raise ValueError(
            "Model action space does not match the environment action space."
        )


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    env = CICDPipelineEnv(args.csv_path)
    try:
        model = DQN.load(str(args.model_path))
        validate_model(model, env)

        observation, _ = env.reset(seed=args.seed)
        if args.recommendation_file is not None:
            predicted_action, _ = model.predict(observation, deterministic=True)
            action = PipelineAction(int(predicted_action))
            _, reward, _, _, _ = env.step(int(action))
            args.recommendation_file.parent.mkdir(parents=True, exist_ok=True)
            args.recommendation_file.write_text(
                f"{ACTION_NAMES[action]}\n",
                encoding="utf-8",
            )
            print(f"Current State: {format_state(observation)}")
            print(f"Predicted Action: {ACTION_NAMES[action]}")
            print(f"Reward: {reward:.4f}")
            print(f"Recommendation saved to {args.recommendation_file}")
            return

        terminated = False
        truncated = False
        while not (terminated or truncated):
            current_state = observation
            predicted_action, _ = model.predict(
                current_state,
                deterministic=True,
            )
            action = PipelineAction(int(predicted_action))
            observation, reward, terminated, truncated, _ = env.step(int(action))
            print(f"Current State: {format_state(current_state)}")
            print(f"Predicted Action: {ACTION_NAMES[action]}")
            print(f"Reward: {reward:.4f}")
            print()
    finally:
        env.close()


if __name__ == "__main__":
    main()
