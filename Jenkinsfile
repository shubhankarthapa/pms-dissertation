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
        APP_CONTAINER_NAME = "pms-app-ci-${BUILD_NUMBER}-${EXECUTOR_NUMBER}"
        METRICS_CONTAINER_NAME = "pms-metrics-ci-${BUILD_NUMBER}-${EXECUTOR_NUMBER}"
    }

    stages {
        stage('Checkout Source Code') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    long buildStartedAt = System.currentTimeMillis()
                    env.BUILD_STARTED_AT = "${buildStartedAt}"
                    try {
                        sh 'docker build --tag "$DOCKER_IMAGE" .'
                    } finally {
                        env.BUILD_TIME_SECONDS = "${Math.round((System.currentTimeMillis() - buildStartedAt) / 1000.0)}"
                    }
                }
            }
        }

        stage('Verify Image Dependencies') {
            steps {
                sh 'docker run --rm --entrypoint python "$DOCKER_IMAGE" -m pip check'
            }
        }

        stage('Run Migrations and Collect Static Files') {
            steps {
                sh '''
                    docker rm --force "$CI_CONTAINER_NAME" >/dev/null 2>&1 || true
                    docker run --rm --name "$CI_CONTAINER_NAME" \\
                        --env DJANGO_DEBUG="$DJANGO_DEBUG" \\
                        --env DJANGO_SECRET_KEY="$DJANGO_SECRET_KEY" \\
                        --env DJANGO_ALLOWED_HOSTS="$DJANGO_ALLOWED_HOSTS" \\
                        --env DB_ENGINE="$DB_ENGINE" \\
                        --entrypoint sh \\
                        "$DOCKER_IMAGE" -ec \\
                        'python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py check'
                '''
            }
        }

        stage('Run Unit Tests') {
            steps {
                script {
                    long testStartedAt = System.currentTimeMillis()
                    try {
                        sh '''
                            docker rm --force "$CI_CONTAINER_NAME" >/dev/null 2>&1 || true
                            docker run --rm --name "$CI_CONTAINER_NAME" \\
                                --env DJANGO_DEBUG="$DJANGO_DEBUG" \\
                                --env DJANGO_SECRET_KEY="$DJANGO_SECRET_KEY" \\
                                --env DJANGO_ALLOWED_HOSTS="$DJANGO_ALLOWED_HOSTS" \\
                                --env DB_ENGINE="$DB_ENGINE" \\
                                --entrypoint python \\
                                "$DOCKER_IMAGE" manage.py test --verbosity 2
                        '''
                    } finally {
                        env.TEST_TIME_SECONDS = "${Math.round((System.currentTimeMillis() - testStartedAt) / 1000.0)}"
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
                            docker rm --force "$APP_CONTAINER_NAME" >/dev/null 2>&1 || true
                            docker run --detach --name "$APP_CONTAINER_NAME" \\
                                --env DJANGO_DEBUG=True \\
                                --env DJANGO_SECRET_KEY=jenkins-ci-only-secret-key \\
                                --env DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver \\
                                --env DB_ENGINE=sqlite \\
                                "$DOCKER_IMAGE"

                            attempt=0
                            while [ "$attempt" -lt 60 ]; do
                                if ! docker inspect "$APP_CONTAINER_NAME" >/dev/null 2>&1; then
                                    docker logs "$APP_CONTAINER_NAME" 2>&1 || true
                                    exit 1
                                fi
                                if docker logs "$APP_CONTAINER_NAME" 2>&1 | grep -q 'Starting development server at'; then
                                    docker logs "$APP_CONTAINER_NAME"
                                    exit 0
                                fi
                                running=$(docker inspect --format='{{.State.Running}}' "$APP_CONTAINER_NAME")
                                if [ "$running" != true ]; then
                                    docker logs "$APP_CONTAINER_NAME"
                                    exit 1
                                fi
                                attempt=$((attempt + 1))
                                sleep 1
                            done

                            docker logs "$APP_CONTAINER_NAME"
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
                    sh '''
                        set -eu
                        docker rm --force "$METRICS_CONTAINER_NAME" >/dev/null 2>&1 || true
                        docker run --detach --name "$METRICS_CONTAINER_NAME" \\
                            --entrypoint sleep "$DOCKER_IMAGE" infinity
                        if [ -f "$WORKSPACE/metrics.csv" ]; then
                            docker cp "$WORKSPACE/metrics.csv" "$METRICS_CONTAINER_NAME:/app/metrics.csv"
                            docker exec --user 0 "$METRICS_CONTAINER_NAME" chown django:django /app/metrics.csv
                        fi
                        if [ -f "$WORKSPACE/pipeline-results.log" ]; then
                            docker cp "$WORKSPACE/pipeline-results.log" "$METRICS_CONTAINER_NAME:/app/pipeline-results.log"
                            docker exec --user 0 "$METRICS_CONTAINER_NAME" chown django:django /app/pipeline-results.log
                        fi
                        docker exec "$METRICS_CONTAINER_NAME" python scripts/collect_metrics.py \\
                            --build-time "${BUILD_TIME_SECONDS:-0}" \\
                            --test-time "${TEST_TIME_SECONDS:-0}" \\
                            --deploy-time "${DEPLOY_TIME_SECONDS:-0}" \\
                            --success '1' \\
                            --build-number "$BUILD_NUMBER" \\
                            --result 'SUCCESS' \\
                            --metrics-file /app/metrics.csv \\
                            --log-file /app/pipeline-results.log
                        docker cp "$METRICS_CONTAINER_NAME:/app/metrics.csv" "$WORKSPACE/metrics.csv"
                        docker cp "$METRICS_CONTAINER_NAME:/app/pipeline-results.log" "$WORKSPACE/pipeline-results.log"
                        docker rm --force "$METRICS_CONTAINER_NAME" >/dev/null
                    '''
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
                        withEnv(["PIPELINE_RESULT=${result}", "PIPELINE_SUCCESS=${success}"]) {
                            sh '''
                                set -eu
                                if docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
                                    docker rm --force "$METRICS_CONTAINER_NAME" >/dev/null 2>&1 || true
                                    docker run --detach --name "$METRICS_CONTAINER_NAME" \\
                                        --entrypoint sleep "$DOCKER_IMAGE" infinity
                                    if [ -f "$WORKSPACE/metrics.csv" ]; then
                                        docker cp "$WORKSPACE/metrics.csv" "$METRICS_CONTAINER_NAME:/app/metrics.csv"
                                        docker exec --user 0 "$METRICS_CONTAINER_NAME" chown django:django /app/metrics.csv
                                    fi
                                    if [ -f "$WORKSPACE/pipeline-results.log" ]; then
                                        docker cp "$WORKSPACE/pipeline-results.log" "$METRICS_CONTAINER_NAME:/app/pipeline-results.log"
                                        docker exec --user 0 "$METRICS_CONTAINER_NAME" chown django:django /app/pipeline-results.log
                                    fi
                                    docker exec "$METRICS_CONTAINER_NAME" python scripts/collect_metrics.py \\
                                        --build-time "${BUILD_TIME_SECONDS:-0}" \\
                                        --test-time "${TEST_TIME_SECONDS:-0}" \\
                                        --deploy-time "${DEPLOY_TIME_SECONDS:-0}" \\
                                        --success "$PIPELINE_SUCCESS" \\
                                        --build-number "$BUILD_NUMBER" \\
                                        --result "$PIPELINE_RESULT" \\
                                        --metrics-file /app/metrics.csv \\
                                        --log-file /app/pipeline-results.log
                                    docker cp "$METRICS_CONTAINER_NAME:/app/metrics.csv" "$WORKSPACE/metrics.csv"
                                    docker cp "$METRICS_CONTAINER_NAME:/app/pipeline-results.log" "$WORKSPACE/pipeline-results.log"
                                    docker rm --force "$METRICS_CONTAINER_NAME" >/dev/null
                                else
                                    echo 'Metrics were not collected because the Django image was not built.'
                                fi
                            '''
                        }
                    }
                } finally {
                    archiveArtifacts artifacts: 'metrics.csv,pipeline-results.log', allowEmptyArchive: true
                    sh 'docker rm --force "$APP_CONTAINER_NAME" >/dev/null 2>&1 || true'
                    sh 'docker rm --force "$CI_CONTAINER_NAME" >/dev/null 2>&1 || true'
                    sh 'docker rm --force "$METRICS_CONTAINER_NAME" >/dev/null 2>&1 || true'
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