"""Evaluate the trained DQN policy and export per-pipeline results."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Sequence

from stable_baselines3 import DQN

if __package__:
    from .environment import CICDPipelineEnv
else:
    from environment import CICDPipelineEnv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS_PATH = PROJECT_ROOT / "metrics_traditional.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "rl_model.zip"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "metrics_rl.csv"
RESULT_FIELDS = (
    "build_time",
    "test_time",
    "deploy_time",
    "success",
    "chosen_action",
    "reward",
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
        help="Path to the trained DQN model",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the evaluation CSV (default: metrics_rl.csv)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Environment random seed")
    return parser.parse_args(argv)


def evaluate(
    model: DQN,
    env: CICDPipelineEnv,
    *,
    seed: int,
) -> list[dict[str, float | int | str]]:
    if model.observation_space.shape != env.observation_space.shape:
        raise ValueError(
            "Model observation shape "
            f"{model.observation_space.shape} does not match environment "
            f"shape {env.observation_space.shape}; retrain the model."
        )
    if model.action_space != env.action_space:
        raise ValueError("Model action space does not match the environment.")

    observation, _ = env.reset(seed=seed)
    terminated = False
    truncated = False
    results: list[dict[str, float | int | str]] = []

    while not (terminated or truncated):
        action_value, _ = model.predict(observation, deterministic=True)
        action = int(action_value)
        _, reward, terminated, truncated, info = env.step(action)
        results.append(
            {
                "build_time": info["build_time"],
                "test_time": info["test_time"],
                "deploy_time": info["deploy_time"],
                "success": int(info["success"]),
                "chosen_action": info["action_name"],
                "reward": reward,
            }
        )

    return results


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    env = CICDPipelineEnv(args.csv_path)
    try:
        model = DQN.load(str(args.model_path))
        results = evaluate(model, env, seed=args.seed)
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        with args.output_path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=RESULT_FIELDS)
            writer.writeheader()
            writer.writerows(results)
    finally:
        env.close()

    print(f"Evaluated {len(results)} states.")
    print(f"Results saved to {args.output_path}")


if __name__ == "__main__":
    main()
