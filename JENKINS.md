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

## Results

Each build appends one row to `metrics.csv`:

```csv
build_time,test_time,deploy_time,success
120,35,12,1
```

Times are rounded seconds. `success` is `1` for a successful build and `0` otherwise. Jenkins also appends build number, result, and timings to `pipeline-results.log`. Both files are archived as build artifacts; inspect the build's **Console Output** for stage logs and test details.