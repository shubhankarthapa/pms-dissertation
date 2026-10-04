"""Train a DQN policy for the CI/CD pipeline environment."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Sequence

from stable_baselines3 import DQN

from environment import CICDPipelineEnv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS_PATH = PROJECT_ROOT / "metrics_traditional.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "rl_model.zip"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_METRICS_PATH,
        help="Path to metrics_traditional.csv",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Path for the saved Stable-Baselines3 model",
    )
    parser.add_argument(
        "--timesteps",
        type=int,
        default=10_000,
        help="Number of environment timesteps to train (default: 10000)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args(argv)
    if args.timesteps <= 0:
        parser.error("--timesteps must be greater than zero")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)
    args = parse_args(argv)

    logger.info("Loading traditional CI metrics from %s", args.csv_path)
    env = CICDPipelineEnv(args.csv_path)
    try:
        logger.info(
            "Starting DQN training for %d timesteps with seed %d",
            args.timesteps,
            args.seed,
        )
        model = DQN(
            policy="MlpPolicy",
            env=env,
            verbose=1,
            seed=args.seed,
        )
        model.learn(total_timesteps=args.timesteps, log_interval=10)

        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(args.output_path))
        logger.info("Saved trained model to %s", args.output_path)
    finally:
        env.close()


if __name__ == "__main__":
    main()
