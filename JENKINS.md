# Jenkins CI/CD

## Requirements

- A Jenkins controller with the Pipeline, Git, and Timestamper plugins
- A Linux Jenkins agent with Git and Docker installed; Python is not required on the agent
- Permission for the Jenkins agent account to access the Docker daemon

The agent must be able to build and start Docker containers, pull `python:3.12-slim`, and bind-mount its Jenkins workspace into those containers. The pipeline installs dependencies and runs all Python commands inside Docker.

## Configure a pipeline

1. Push this project to a Git repository accessible by Jenkins.
2. In Jenkins, choose **New Item**, select **Pipeline** (or **Multibranch Pipeline**), and configure the repository as the source. Ensure its agent has Docker access.
3. Set the pipeline definition to **Pipeline script from SCM**, select Git, enter the repository URL and credentials if needed, and set the script path to `Jenkinsfile`.
4. Save and run **Build Now**.

No Django or Docker secrets are required for CI. The pipeline uses SQLite and a CI-only secret key. It runs Django's unit tests, checks settings and static collection, builds the image, then starts it and waits for Django's development server to report ready. The started container is removed after the pipeline.

## RL pipeline recommendation

Before migrations and Django tests, Jenkins runs `rl/predict.py` with the
trained `rl_model.zip` and historical `metrics_traditional.csv`. The script
uses the current model and environment to select one action, writes its display
name to `recommendation.txt`, and prints the selected action and state in the
Jenkins console. Jenkins validates and logs the action, then archives
`recommendation.txt` as a build artifact. The recommendation file is
workspace-generated and is ignored by Git.

Both input files must be available at the repository root after Jenkins
checkout. If the trained model or historical dataset is stored outside source
control, provision it into the workspace before the recommendation stage (for
example, from a controlled Jenkins artifact store). Prediction fails the build
if either file is missing or if the model's observation/action spaces do not
match the environment; it does not silently substitute a default action.

At this integration stage, Jenkins records and logs the recommended strategy;
it does not yet alter test parallelism, caching, or other build behavior based
on that recommendation. The existing `metrics.csv` collection and
`pipeline-results.log` flow remain unchanged.

## Results

Each build appends one row to `metrics.csv`:

```csv
build_time,test_time,deploy_time,success
120,35,12,1
```

Times are rounded seconds. `success` is `1` for a successful build and `0` otherwise. Jenkins also appends build number, result, and timings to `pipeline-results.log`. Both files are archived as build artifacts; inspect the build's **Console Output** for stage logs and test details.