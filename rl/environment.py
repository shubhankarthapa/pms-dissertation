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
    """Available pipeline optimization strategies."""

    STANDARD = 0
    CACHE = 1
    PARALLEL_TESTS = 2
    CACHE_AND_PARALLEL_TESTS = 3
    SECURITY_SCAN = 4
    FAST_BUILD = 5
    RESOURCE_OPTIMIZED = 6


class CICDPipelineEnv(gym.Env[np.ndarray, int]):
    """Replay traditional CI measurements with configurable action trade-offs.

    The CSV must contain ``build_time``, ``test_time``, ``deploy_time``, and
    ``success``. Optional ``cpu_usage`` and ``memory_usage`` columns are
    percentages; when absent, resource use is estimated from the workload.
    Observations are normalized to [0, 1] in the order build time, test time,
    deploy time, CPU, memory, and baseline success.
    """

    metadata = {"render_modes": []}

    _REQUIRED_COLUMNS = ("build_time", "test_time", "deploy_time", "success")
    _ACTION_NAMES = {
        PipelineAction.STANDARD: "Standard Pipeline",
        PipelineAction.CACHE: "Enable Cache",
        PipelineAction.PARALLEL_TESTS: "Parallel Testing",
        PipelineAction.CACHE_AND_PARALLEL_TESTS: "Cache + Parallel Testing",
        PipelineAction.SECURITY_SCAN: "Security Scan",
        PipelineAction.FAST_BUILD: "Fast Build Mode",
        PipelineAction.RESOURCE_OPTIMIZED: "Resource Optimized Mode",
    }
    _TIME_REWARD_WEIGHTS = (0.35, 0.35, 0.20)
    _RESOURCE_REWARD_WEIGHT = 0.60

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
        self.csv_path = (
            Path(csv_path)
            if csv_path is not None
            else Path(__file__).resolve().parents[1] / "metrics_traditional.csv"
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

        max_build_time = max(row[0] for row in self._metrics)
        max_test_time = max(row[1] for row in self._metrics)
        max_deploy_time = max(row[2] for row in self._metrics)
        self.build_time_scale = self._validate_scale(
            "build_time_scale", build_time_scale, max_build_time * 1.15
        )
        self.test_time_scale = self._validate_scale(
            "test_time_scale", test_time_scale, max_test_time
        )
        self.deploy_time_scale = self._validate_scale(
            "deploy_time_scale", deploy_time_scale, max_deploy_time
        )

        self.action_space = spaces.Discrete(len(self._ACTION_NAMES))
        self.observation_space = spaces.Box(
            low=np.zeros(6, dtype=np.float32),
            high=np.ones(6, dtype=np.float32),
            dtype=np.float32,
        )
        self._order: np.ndarray | None = None
        self._episode_step = 0

    @staticmethod
    def _validate_reduction(name: str, value: float) -> None:
        if not np.isfinite(value) or not 0.0 <= value < 1.0:
            raise ValueError(f"{name} must be finite and in the range [0, 1)")

    @staticmethod
    def _validate_scale(name: str, requested: float | None, maximum: float) -> float:
        scale = max(maximum, 1.0) if requested is None else float(requested)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError(f"{name} must be finite and greater than zero")
        return scale

    @classmethod
    def _load_metrics(
        cls, csv_path: Path
    ) -> list[tuple[float, float, float, float, float, bool]]:
        if not csv_path.is_file():
            raise FileNotFoundError(
                f"Metrics CSV not found: {csv_path}. "
                "Provide csv_path or place metrics_traditional.csv in the project root."
            )

        raw_rows: list[tuple[float, float, float, float | None, float | None, bool]] = []
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
                    cpu_usage = cls._optional_percentage(
                        row, columns.get("cpu_usage"), "cpu_usage", line_number
                    )
                    memory_usage = cls._optional_percentage(
                        row, columns.get("memory_usage"), "memory_usage", line_number
                    )
                except (AttributeError, TypeError, ValueError) as error:
                    raise ValueError(
                        "Invalid build_time, test_time, deploy_time, cpu_usage, "
                        f"or memory_usage on CSV line {line_number}"
                    ) from error

                for name, value in (
                    ("build_time", build_time),
                    ("test_time", test_time),
                    ("deploy_time", deploy_time),
                ):
                    if not np.isfinite(value) or value < 0:
                        raise ValueError(
                            f"{name} must be finite and non-negative on CSV line {line_number}"
                        )
                if success_value in {"1", "true", "yes", "success", "passed"}:
                    success = True
                elif success_value in {"0", "false", "no", "failure", "failed"}:
                    success = False
                else:
                    raise ValueError(
                        f"success must be a boolean or 0/1 on CSV line {line_number}"
                    )
                raw_rows.append(
                    (
                        build_time,
                        test_time,
                        deploy_time,
                        cpu_usage,
                        memory_usage,
                        success,
                    )
                )

        if not raw_rows:
            raise ValueError(f"Metrics CSV contains no data rows: {csv_path}")

        max_build_time = max(row[0] for row in raw_rows) or 1.0
        max_test_time = max(row[1] for row in raw_rows) or 1.0
        rows: list[tuple[float, float, float, float, float, bool]] = []
        for build_time, test_time, deploy_time, cpu, memory, success in raw_rows:
            estimated_cpu = 25.0 + 25.0 * (
                build_time / max_build_time + test_time / max_test_time
            )
            estimated_memory = 30.0 + 40.0 * build_time / max_build_time
            rows.append(
                (
                    build_time,
                    test_time,
                    deploy_time,
                    estimated_cpu if cpu is None else cpu,
                    estimated_memory if memory is None else memory,
                    success,
                )
            )
        return rows

    @staticmethod
    def _optional_percentage(
        row: dict[str, str],
        column: str | None,
        name: str,
        line_number: int,
    ) -> float | None:
        if column is None or not row.get(column, "").strip():
            return None
        value = float(row[column].strip())
        if not np.isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError(
                f"{name} must be finite and between 0 and 100 on CSV line {line_number}"
            )
        return value

    def _normalize(
        self,
        build_time: float,
        test_time: float,
        deploy_time: float,
        cpu_usage: float,
        memory_usage: float,
        success: bool,
    ) -> np.ndarray:
        return np.array(
            [
                np.clip(build_time / self.build_time_scale, 0.0, 1.0),
                np.clip(test_time / self.test_time_scale, 0.0, 1.0),
                np.clip(deploy_time / self.deploy_time_scale, 0.0, 1.0),
                np.clip(cpu_usage / 100.0, 0.0, 1.0),
                np.clip(memory_usage / 100.0, 0.0, 1.0),
                float(success),
            ],
            dtype=np.float32,
        )

    def _observation(self, row_index: int) -> np.ndarray:
        return self._normalize(*self._metrics[row_index])

    def _apply_action(
        self,
        action: PipelineAction,
        build_time: float,
        test_time: float,
        cpu_usage: float,
        memory_usage: float,
    ) -> tuple[float, float, float, float]:
        if action in {
            PipelineAction.CACHE,
            PipelineAction.CACHE_AND_PARALLEL_TESTS,
        }:
            build_time *= 1.0 - self.cache_build_reduction
            memory_usage *= 1.20
        if action in {
            PipelineAction.PARALLEL_TESTS,
            PipelineAction.CACHE_AND_PARALLEL_TESTS,
        }:
            test_time *= 1.0 - self.parallel_test_reduction
            cpu_usage *= 1.30
        if action is PipelineAction.SECURITY_SCAN:
            build_time *= 1.15
        elif action is PipelineAction.FAST_BUILD:
            build_time *= 0.75
        elif action is PipelineAction.RESOURCE_OPTIMIZED:
            build_time *= 1.05
            cpu_usage *= 0.70
        return (
            build_time,
            test_time,
            min(cpu_usage, 100.0),
            min(memory_usage, 100.0),
        )

    @staticmethod
    def _success_probability(action: PipelineAction, baseline_success: bool) -> float:
        probability = 0.95 if baseline_success else 0.15
        if action is PipelineAction.SECURITY_SCAN:
            probability += 0.10
        elif action is PipelineAction.FAST_BUILD:
            probability -= 0.20
        return float(np.clip(probability, 0.0, 1.0))

    def calculate_reward(
        self,
        build_time: float,
        test_time: float,
        success: bool,
        *,
        deploy_time: float = 0.0,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
    ) -> float:
        """Reward fast, successful builds while penalizing deployment and resources.

        Time costs are linear in their normalized values. CPU and memory costs
        are quadratic so using already-busy resources is more expensive.
        """
        time_cost = (
            self._TIME_REWARD_WEIGHTS[0] * build_time / self.build_time_scale
            + self._TIME_REWARD_WEIGHTS[1] * test_time / self.test_time_scale
            + self._TIME_REWARD_WEIGHTS[2] * deploy_time / self.deploy_time_scale
        )
        cpu_cost = self._RESOURCE_REWARD_WEIGHT * (cpu_usage / 100.0) ** 2
        memory_cost = self._RESOURCE_REWARD_WEIGHT * (memory_usage / 100.0) ** 2
        outcome_reward = self.success_bonus if success else -self.failure_penalty
        return float(outcome_reward - time_cost - cpu_cost - memory_cost)

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
        (
            baseline_build,
            baseline_test,
            deploy_time,
            baseline_cpu,
            baseline_memory,
            baseline_success,
        ) = self._metrics[row_index]
        pipeline_action = PipelineAction(int(action))
        actual_build, actual_test, actual_cpu, actual_memory = self._apply_action(
            pipeline_action,
            baseline_build,
            baseline_test,
            baseline_cpu,
            baseline_memory,
        )
        success_probability = self._success_probability(
            pipeline_action, baseline_success
        )
        success = bool(self.np_random.random() < success_probability)
        reward = self.calculate_reward(
            actual_build,
            actual_test,
            success,
            deploy_time=deploy_time,
            cpu_usage=actual_cpu,
            memory_usage=actual_memory,
        )

        self._episode_step += 1
        terminated = self._episode_step == len(self._order)
        if terminated:
            observation = self._normalize(
                actual_build,
                actual_test,
                deploy_time,
                actual_cpu,
                actual_memory,
                success,
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
            "cpu_usage": actual_cpu,
            "memory_usage": actual_memory,
            "success": success,
            "success_probability": success_probability,
        }
        return observation, reward, terminated, False, info
