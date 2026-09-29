pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        DJANGO_DEBUG = 'True'
        DJANGO_SECRET_KEY = 'jenkins-ci-only-secret-key'
        DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,testserver'
        DB_ENGINE = 'sqlite'
        DOCKER_IMAGE = "pms-django:${BUILD_NUMBER}"
        CI_CONTAINER_NAME = "pms-ci-${BUILD_NUMBER}-${EXECUTOR_NUMBER}"
    }

    stages {
        stage('Checkout Source Code') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                    python3 -m venv .venv
                    .venv/bin/python -m pip install --upgrade pip
                    .venv/bin/python -m pip install -r requirements.txt
                '''
            }
        }

        stage('Run Unit Tests') {
            steps {
                script {
                    long testStartedAt = System.currentTimeMillis()
                    try {
                        sh '.venv/bin/python manage.py test --verbosity 2'
                    } finally {
                        env.TEST_TIME_SECONDS = "${Math.round((System.currentTimeMillis() - testStartedAt) / 1000.0)}"
                    }
                }
            }
        }

        stage('Build Django Application') {
            steps {
                script {
                    env.BUILD_STARTED_AT = "${System.currentTimeMillis()}"
                }
                sh '''
                    .venv/bin/python manage.py check
                    .venv/bin/python manage.py collectstatic --noinput
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    long buildStartedAt = env.BUILD_STARTED_AT
                        ? env.BUILD_STARTED_AT.toLong()
                        : System.currentTimeMillis()
                    try {
                        sh 'docker build --tag "$DOCKER_IMAGE" .'
                    } finally {
                        env.BUILD_TIME_SECONDS = "${Math.round((System.currentTimeMillis() - buildStartedAt) / 1000.0)}"
                    }
                }
            }
        }

        stage('Run Docker Container') {
            steps {
                script {
                    long deployStartedAt = System.currentTimeMillis()
                    try {
                        sh '''
                            set -eu
                            docker rm --force "$CI_CONTAINER_NAME" >/dev/null 2>&1 || true
                            docker run --detach --name "$CI_CONTAINER_NAME" \\
                                --env DJANGO_DEBUG=True \\
                                --env DJANGO_SECRET_KEY=jenkins-ci-only-secret-key \\
                                --env DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver \\
                                --env DB_ENGINE=sqlite \\
                                "$DOCKER_IMAGE"

                            attempt=0
                            while [ "$attempt" -lt 60 ]; do
                                if ! docker inspect "$CI_CONTAINER_NAME" >/dev/null 2>&1; then
                                    docker logs "$CI_CONTAINER_NAME" 2>&1 || true
                                    exit 1
                                fi
                                if docker logs "$CI_CONTAINER_NAME" 2>&1 | grep -q 'Starting development server at'; then
                                    docker logs "$CI_CONTAINER_NAME"
                                    exit 0
                                fi
                                running=$(docker inspect --format='{{.State.Running}}' "$CI_CONTAINER_NAME")
                                if [ "$running" != true ]; then
                                    docker logs "$CI_CONTAINER_NAME"
                                    exit 1
                                fi
                                attempt=$((attempt + 1))
                                sleep 1
                            done

                            docker logs "$CI_CONTAINER_NAME"
                            echo 'Container did not start Django within 60 seconds.'
                            exit 1
                        '''
                    } finally {
                        env.DEPLOY_TIME_SECONDS = "${Math.round((System.currentTimeMillis() - deployStartedAt) / 1000.0)}"
                    }
                }
            }
        }

        stage('Collect Build Metrics') {
            steps {
                script {
                    sh """
                        python3 scripts/collect_metrics.py \\
                            --build-time '${env.BUILD_TIME_SECONDS ?: '0'}' \\
                            --test-time '${env.TEST_TIME_SECONDS ?: '0'}' \\
                            --deploy-time '${env.DEPLOY_TIME_SECONDS ?: '0'}' \\
                            --success '1' \\
                            --build-number '${env.BUILD_NUMBER}' \\
                            --result 'SUCCESS'
                    """
                    env.METRICS_COLLECTED = 'true'
                }
            }
        }
    }

    post {
        always {
            script {
                if (!env.BUILD_TIME_SECONDS && env.BUILD_STARTED_AT) {
                    env.BUILD_TIME_SECONDS = "${Math.round((System.currentTimeMillis() - env.BUILD_STARTED_AT.toLong()) / 1000.0)}"
                }

                String result = currentBuild.currentResult ?: 'FAILURE'
                String success = result == 'SUCCESS' ? '1' : '0'
                try {
                    if (env.METRICS_COLLECTED != 'true') {
                        sh """
                            python3 scripts/collect_metrics.py \\
                                --build-time '${env.BUILD_TIME_SECONDS ?: '0'}' \\
                                --test-time '${env.TEST_TIME_SECONDS ?: '0'}' \\
                                --deploy-time '${env.DEPLOY_TIME_SECONDS ?: '0'}' \\
                                --success '${success}' \\
                                --build-number '${env.BUILD_NUMBER}' \\
                                --result '${result}'
                        """
                    }
                } finally {
                    archiveArtifacts artifacts: 'metrics.csv,pipeline-results.log', allowEmptyArchive: true
                    sh 'docker rm --force "$CI_CONTAINER_NAME" >/dev/null 2>&1 || true'
                    sh 'docker image rm "$DOCKER_IMAGE" >/dev/null 2>&1 || true'
                }
            }
        }
        success {
            echo 'Pipeline completed successfully.'
        }
        failure {
            echo 'Pipeline failed. Review this build’s Console Output and pipeline-results.log.'
        }
    }
}