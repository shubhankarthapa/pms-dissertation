"""Gymnasium environment for choosing CI/CD pipeline optimizations."""

from __future__ import annotations

import csv
from enum import IntEnum
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces


class PipelineAction(IntEnum):
    """Available pipeline configurations."""

    STANDARD = 0
    CACHE = 1
    PARALLEL_TESTS = 2
    CACHE_AND_PARALLEL_TESTS = 3


class CICDPipelineEnv(gym.Env[np.ndarray, int]):
    """Replay traditional CI measurements with configurable action speedups.

    The input CSV must contain ``build_time``, ``test_time``, ``deploy_time``,
    and ``success`` columns. Each episode visits every data row once in a
    shuffled order. Actions simulate cache and parallel-test time reductions;
    success is preserved from the traditional measurement because no
    action-specific reliability data is available.
    """

    metadata = {"render_modes": []}

    _REQUIRED_COLUMNS = ("build_time", "test_time", "deploy_time", "success")
    _ACTION_NAMES = {
        PipelineAction.STANDARD: "Standard Pipeline",
        PipelineAction.CACHE: "Enable Cache",
        PipelineAction.PARALLEL_TESTS: "Parallel Test Execution",
        PipelineAction.CACHE_AND_PARALLEL_TESTS: "Cache + Parallel Testing",
    }

    def __init__(
        self,
        csv_path: str | Path | None = None,
        *,
        cache_build_reduction: float = 0.20,
        parallel_test_reduction: float = 0.30,
        success_bonus: float = 1.0,
        failure_penalty: float = 1.0,
        build_time_scale: float | None = None,
        test_time_scale: float | None = None,
        deploy_time_scale: float | None = None,
    ) -> None:
        super().__init__()
        self.csv_path = Path(csv_path) if csv_path is not None else (
            Path(__file__).resolve().parents[1] / "metrics_traditional.csv"
        )
        self._validate_reduction("cache_build_reduction", cache_build_reduction)
        self._validate_reduction("parallel_test_reduction", parallel_test_reduction)
        if (
            not np.isfinite(success_bonus)
            or not np.isfinite(failure_penalty)
            or success_bonus < 0
            or failure_penalty < 0
        ):
            raise ValueError(
                "success_bonus and failure_penalty must be finite and non-negative"
            )

        self.cache_build_reduction = float(cache_build_reduction)
        self.parallel_test_reduction = float(parallel_test_reduction)
        self.success_bonus = float(success_bonus)
        self.failure_penalty = float(failure_penalty)
        self._metrics = self._load_metrics(self.csv_path)

        mean_build_time = float(np.mean([row[0] for row in self._metrics]))
        mean_test_time = float(np.mean([row[1] for row in self._metrics]))
        mean_deploy_time = float(np.mean([row[2] for row in self._metrics]))
        self.build_time_scale = self._validate_scale(
            "build_time_scale", build_time_scale, mean_build_time
        )
        self.test_time_scale = self._validate_scale(
            "test_time_scale", test_time_scale, mean_test_time
        )
        self.deploy_time_scale = self._validate_scale(
            "deploy_time_scale", deploy_time_scale, mean_deploy_time
        )

        self.action_space = spaces.Discrete(len(self._ACTION_NAMES))
        self.observation_space = spaces.Box(
            low=np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32),
            high=np.array(
                [
                    max(row[0] for row in self._metrics),
                    max(row[1] for row in self._metrics),
                    max(row[2] for row in self._metrics),
                    1.0,
                ],
                dtype=np.float32,
            ),
            dtype=np.float32,
        )
        self._order: np.ndarray | None = None
        self._episode_step = 0

    @staticmethod
    def _validate_reduction(name: str, value: float) -> None:
        if not np.isfinite(value) or not 0.0 <= value < 1.0:
            raise ValueError(f"{name} must be finite and in the range [0, 1)")

    @staticmethod
    def _validate_scale(
        name: str, requested: float | None, mean_time: float
    ) -> float:
        scale = max(mean_time, 1.0) if requested is None else float(requested)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError(f"{name} must be finite and greater than zero")
        return scale

    @classmethod
    def _load_metrics(
        cls, csv_path: Path
    ) -> list[tuple[float, float, float, bool]]:
        if not csv_path.is_file():
            raise FileNotFoundError(
                f"Metrics CSV not found: {csv_path}. "
                "Provide csv_path or place metrics_traditional.csv in the project root."
            )

        rows: list[tuple[float, float, float, bool]] = []
        with csv_path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError(f"Metrics CSV has no header: {csv_path}")

            columns = {
                name.strip().lower(): name
                for name in reader.fieldnames
                if name is not None
            }
            missing = set(cls._REQUIRED_COLUMNS) - columns.keys()
            if missing:
                raise ValueError(
                    f"Metrics CSV is missing required columns: {', '.join(sorted(missing))}"
                )

            for line_number, row in enumerate(reader, start=2):
                try:
                    build_time = float(row[columns["build_time"]].strip())
                    test_time = float(row[columns["test_time"]].strip())
                    deploy_time = float(row[columns["deploy_time"]].strip())
                    success_value = row[columns["success"]].strip().lower()
                except (AttributeError, TypeError, ValueError) as error:
                    raise ValueError(
                        "Invalid build_time, test_time, or deploy_time "
                        f"on CSV line {line_number}"
                    ) from error

                if not np.isfinite(build_time) or build_time < 0:
                    raise ValueError(
                        f"build_time must be finite and non-negative on CSV line {line_number}"
                    )
                if not np.isfinite(test_time) or test_time < 0:
                    raise ValueError(
                        f"test_time must be finite and non-negative on CSV line {line_number}"
                    )
                if not np.isfinite(deploy_time) or deploy_time < 0:
                    raise ValueError(
                        f"deploy_time must be finite and non-negative on CSV line {line_number}"
                    )
                if success_value in {"1", "true", "yes", "success", "passed"}:
                    success = True
                elif success_value in {"0", "false", "no", "failure", "failed"}:
                    success = False
                else:
                    raise ValueError(
                        f"success must be a boolean or 0/1 on CSV line {line_number}"
                    )
                rows.append((build_time, test_time, deploy_time, success))

        if not rows:
            raise ValueError(f"Metrics CSV contains no data rows: {csv_path}")
        return rows

    def _observation(self, row_index: int) -> np.ndarray:
        build_time, test_time, deploy_time, success = self._metrics[row_index]
        return np.array(
            [build_time, test_time, deploy_time, float(success)],
            dtype=np.float32,
        )

    def _apply_action(
        self, action: PipelineAction, build_time: float, test_time: float
    ) -> tuple[float, float]:
        if action in {
            PipelineAction.CACHE,
            PipelineAction.CACHE_AND_PARALLEL_TESTS,
        }:
            build_time *= 1.0 - self.cache_build_reduction
        if action in {
            PipelineAction.PARALLEL_TESTS,
            PipelineAction.CACHE_AND_PARALLEL_TESTS,
        }:
            test_time *= 1.0 - self.parallel_test_reduction
        return build_time, test_time

    def calculate_reward(
        self,
        build_time: float,
        test_time: float,
        success: bool,
        *,
        deploy_time: float = 0.0,
    ) -> float:
        """Reward faster pipeline stages and add a success bonus or failure penalty."""
        time_cost = (
            build_time / self.build_time_scale
            + test_time / self.test_time_scale
            + deploy_time / self.deploy_time_scale
        )
        outcome_reward = self.success_bonus if success else -self.failure_penalty
        return float(-time_cost + outcome_reward)

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        self._order = self.np_random.permutation(len(self._metrics))
        self._episode_step = 0
        row_index = int(self._order[self._episode_step])
        return self._observation(row_index), {"row_index": row_index}

    def step(
        self, action: int
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._order is None:
            raise RuntimeError("Call reset() before step().")
        if self._episode_step >= len(self._order):
            raise RuntimeError("Episode is finished; call reset() before step().")
        if not self.action_space.contains(action):
            raise ValueError(f"Invalid action: {action!r}")

        row_index = int(self._order[self._episode_step])
        baseline_build, baseline_test, deploy_time, success = self._metrics[row_index]
        pipeline_action = PipelineAction(int(action))
        actual_build, actual_test = self._apply_action(
            pipeline_action, baseline_build, baseline_test
        )
        reward = self.calculate_reward(
            actual_build,
            actual_test,
            success,
            deploy_time=deploy_time,
        )

        self._episode_step += 1
        terminated = self._episode_step == len(self._order)
        if terminated:
            observation = np.array(
                [actual_build, actual_test, deploy_time, float(success)],
                dtype=np.float32,
            )
        else:
            next_row_index = int(self._order[self._episode_step])
            observation = self._observation(next_row_index)

        info = {
            "row_index": row_index,
            "action_name": self._ACTION_NAMES[pipeline_action],
            "build_time": actual_build,
            "test_time": actual_test,
            "deploy_time": deploy_time,
            "success": success,
        }
        return observation, reward, terminated, False, info
