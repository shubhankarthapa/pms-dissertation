"""Unit tests for the CI/CD Gymnasium environment."""

import csv
import tempfile
import unittest
from pathlib import Path

import gymnasium as gym
import numpy as np
from stable_baselines3.common.env_checker import check_env

from environment import CICDPipelineEnv, PipelineAction


class CICDPipelineEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "metrics_traditional.csv"
        with self.csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=("build_time", "test_time", "deploy_time", "success"),
            )
            writer.writeheader()
            writer.writerows(
                (
                    {
                        "build_time": 100,
                        "test_time": 50,
                        "deploy_time": 20,
                        "success": 1,
                    },
                    {
                        "build_time": 80,
                        "test_time": 40,
                        "deploy_time": 15,
                        "success": 0,
                    },
                )
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_spaces_and_gymnasium_api(self) -> None:
        env = CICDPipelineEnv(self.csv_path)
        self.assertIsInstance(env, gym.Env)
        self.assertEqual(env.action_space, gym.spaces.Discrete(7))
        self.assertEqual(env.observation_space.shape, (6,))
        check_env(env)
        observation, _ = env.reset(seed=7)
        self.assertTrue(env.observation_space.contains(observation))
        self.assertTrue(np.all(observation >= 0.0))
        self.assertTrue(np.all(observation <= 1.0))
        self.assertEqual(observation.shape, (6,))

    def test_actions_apply_documented_tradeoffs(self) -> None:
        env = CICDPipelineEnv(self.csv_path)
        baseline = (100.0, 50.0, 60.0, 60.0)

        standard = env._apply_action(PipelineAction.STANDARD, *baseline)
        cache = env._apply_action(PipelineAction.CACHE, *baseline)
        parallel = env._apply_action(PipelineAction.PARALLEL_TESTS, *baseline)
        combined = env._apply_action(
            PipelineAction.CACHE_AND_PARALLEL_TESTS, *baseline
        )
        security = env._apply_action(PipelineAction.SECURITY_SCAN, *baseline)
        fast = env._apply_action(PipelineAction.FAST_BUILD, *baseline)
        resource_optimized = env._apply_action(
            PipelineAction.RESOURCE_OPTIMIZED, *baseline
        )

        self.assertEqual(standard, baseline)
        self.assertEqual(cache, (80.0, 50.0, 60.0, 72.0))
        self.assertEqual(parallel, (100.0, 35.0, 78.0, 60.0))
        self.assertEqual(combined, (80.0, 35.0, 78.0, 72.0))
        np.testing.assert_allclose(security, (115.0, 50.0, 60.0, 60.0))
        np.testing.assert_allclose(fast, (75.0, 50.0, 60.0, 60.0))
        np.testing.assert_allclose(
            resource_optimized, (105.0, 50.0, 42.0, 60.0)
        )

    def test_step_returns_raw_metrics_and_normalized_observation(self) -> None:
        env = CICDPipelineEnv(self.csv_path)
        env.reset(seed=1)
        observation, _, _, _, info = env.step(
            PipelineAction.CACHE_AND_PARALLEL_TESTS
        )

        multiplier = 0.8 if info["row_index"] == 0 else 0.64
        test_multiplier = 0.7 if info["row_index"] == 0 else 0.56
        self.assertAlmostEqual(info["build_time"], 100.0 * multiplier)
        self.assertAlmostEqual(info["test_time"], 50.0 * test_multiplier)
        self.assertEqual(info["deploy_time"], 20.0 if info["row_index"] == 0 else 15.0)
        self.assertIn(info["action_name"], ("Cache + Parallel Testing",))
        self.assertIn("cpu_usage", info)
        self.assertIn("memory_usage", info)
        self.assertIn("success_probability", info)
        self.assertTrue(env.observation_space.contains(observation))

    def test_resource_penalties_and_success_outcomes_affect_reward(self) -> None:
        env = CICDPipelineEnv(self.csv_path)
        successful_reward = env.calculate_reward(0, 0, True)
        failed_reward = env.calculate_reward(0, 0, False)
        slower_reward = env.calculate_reward(100, 50, True)
        faster_reward = env.calculate_reward(80, 35, True)
        no_deploy_reward = env.calculate_reward(0, 0, True, deploy_time=0)
        with_deploy_reward = env.calculate_reward(0, 0, True, deploy_time=20)
        low_resource_reward = env.calculate_reward(
            0, 0, True, cpu_usage=20, memory_usage=20
        )
        high_resource_reward = env.calculate_reward(
            0, 0, True, cpu_usage=80, memory_usage=80
        )

        self.assertEqual(successful_reward, 1.0)
        self.assertEqual(failed_reward, -1.0)
        self.assertGreater(faster_reward, slower_reward)
        self.assertGreater(no_deploy_reward, with_deploy_reward)
        self.assertGreater(low_resource_reward, high_resource_reward)
        self.assertEqual(
            CICDPipelineEnv._success_probability(
                PipelineAction.SECURITY_SCAN, False
            ),
            0.25,
        )
        self.assertEqual(
            CICDPipelineEnv._success_probability(PipelineAction.FAST_BUILD, True),
            0.75,
        )

    def test_resource_tradeoffs_change_the_preferred_strategy(self) -> None:
        env = CICDPipelineEnv(self.csv_path)

        def score(action: PipelineAction, cpu: float, memory: float) -> float:
            build, test, actual_cpu, actual_memory = env._apply_action(
                action, 100.0, 50.0, cpu, memory
            )
            return env.calculate_reward(
                build,
                test,
                True,
                deploy_time=20.0,
                cpu_usage=actual_cpu,
                memory_usage=actual_memory,
            )

        self.assertGreater(
            score(PipelineAction.CACHE_AND_PARALLEL_TESTS, 20.0, 20.0),
            score(PipelineAction.STANDARD, 20.0, 20.0),
        )
        self.assertGreater(
            score(PipelineAction.STANDARD, 90.0, 90.0),
            score(PipelineAction.CACHE_AND_PARALLEL_TESTS, 90.0, 90.0),
        )

    def test_resource_columns_are_used_and_validated(self) -> None:
        measured_csv = Path(self.temp_dir.name) / "measured.csv"
        measured_csv.write_text(
            "build_time,test_time,deploy_time,success,cpu_usage,memory_usage\n"
            "100,50,20,1,63,71\n",
            encoding="utf-8",
        )
        env = CICDPipelineEnv(measured_csv)
        self.assertEqual(env._metrics[0][3:5], (63.0, 71.0))

        invalid_csv = Path(self.temp_dir.name) / "invalid_resources.csv"
        invalid_csv.write_text(
            "build_time,test_time,deploy_time,success,cpu_usage\n"
            "100,50,20,1,101\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Invalid build_time"):
            CICDPipelineEnv(invalid_csv)

    def test_invalid_csv_is_rejected(self) -> None:
        bad_csv = Path(self.temp_dir.name) / "invalid.csv"
        bad_csv.write_text("build_time,test_time\n10,5\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "missing required columns"):
            CICDPipelineEnv(bad_csv)


if __name__ == "__main__":
    unittest.main()
