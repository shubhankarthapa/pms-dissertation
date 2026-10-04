"""Unit tests for the CI/CD Gymnasium environment."""

import csv
import tempfile
import unittest
from pathlib import Path

import gymnasium as gym
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
        check_env(env)
        observation, _ = env.reset(seed=7)
        self.assertEqual(env.observation_space.shape, (4,))
        self.assertEqual(len(observation), 4)
        self.assertIn(
            tuple(observation),
            {
                (100.0, 50.0, 20.0, 1.0),
                (80.0, 40.0, 15.0, 0.0),
            },
        )
        self.assertTrue(env.observation_space.contains(observation))

    def test_cache_and_parallel_actions_reduce_expected_metrics(self) -> None:
        env = CICDPipelineEnv(self.csv_path)
        env.reset(seed=1)
        observation, _, _, _, info = env.step(
            PipelineAction.CACHE_AND_PARALLEL_TESTS
        )

        self.assertEqual(info["build_time"], 80.0 if info["row_index"] == 0 else 64.0)
        self.assertEqual(info["test_time"], 35.0 if info["row_index"] == 0 else 28.0)
        self.assertEqual(info["deploy_time"], 20.0 if info["row_index"] == 0 else 15.0)
        self.assertTrue(env.observation_space.contains(observation))
        self.assertEqual(len(observation), 4)
        self.assertEqual(info["action_name"], "Cache + Parallel Testing")

    def test_success_bonus_and_failure_penalty_affect_reward(self) -> None:
        env = CICDPipelineEnv(self.csv_path)
        successful_reward = env.calculate_reward(0, 0, True)
        failed_reward = env.calculate_reward(0, 0, False)
        slower_reward = env.calculate_reward(100, 50, True)
        faster_reward = env.calculate_reward(80, 35, True)
        no_deploy_reward = env.calculate_reward(0, 0, True, deploy_time=0)
        with_deploy_reward = env.calculate_reward(0, 0, True, deploy_time=20)

        self.assertEqual(successful_reward, 1.0)
        self.assertEqual(failed_reward, -1.0)
        self.assertGreater(faster_reward, slower_reward)
        self.assertGreater(no_deploy_reward, with_deploy_reward)

    def test_invalid_csv_is_rejected(self) -> None:
        bad_csv = Path(self.temp_dir.name) / "invalid.csv"
        bad_csv.write_text("build_time,test_time\n10,5\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "missing required columns"):
            CICDPipelineEnv(bad_csv)


if __name__ == "__main__":
    unittest.main()
