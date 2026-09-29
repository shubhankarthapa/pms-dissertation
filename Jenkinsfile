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
    }

    stages {
        stage('Checkout Source Code') {
            steps {
                script {
                    env.CI_PIPELINE_START = sh(script: 'date +%s', returnStdout: true).trim()
                }
                checkout scm
            }
        }

        stage('Create Python Virtual Environment') {
            steps {
                sh 'python3 -m venv .venv'
            }
        }

        stage('Install Requirements') {
            steps {
                sh '''
                    set -eu
                    .venv/bin/python -m pip install --upgrade pip
                    .venv/bin/python -m pip install -r requirements.txt
                '''
            }
        }

        stage('Run Django Migrations') {
            steps {
                sh '.venv/bin/python manage.py migrate --noinput'
            }
        }

        stage('Run Django Tests') {
            steps {
                sh '''
                    set -eu
                    started=$(date +%s)
                    trap 'ended=$(date +%s); echo "$((ended - started))" > "$WORKSPACE/.ci-test-time"' EXIT
                    .venv/bin/python manage.py test --verbosity 2
                '''
            }
        }

        stage('Run Django Check') {
            steps {
                sh '.venv/bin/python manage.py check'
            }
        }

        stage('Collect Metrics') {
            steps {
                sh '''
                    set -eu
                    build_time=0
                    test_time=0
                    if [ -n "${CI_PIPELINE_START:-}" ]; then
                        build_time=$(( $(date +%s) - CI_PIPELINE_START ))
                    fi
                    if [ -f "$WORKSPACE/.ci-test-time" ]; then
                        test_time=$(cat "$WORKSPACE/.ci-test-time")
                    fi
                    .venv/bin/python scripts/collect_metrics.py \\
                        --build-time "$build_time" \\
                        --test-time "$test_time" \\
                        --deploy-time 0 \\
                        --success 1 \\
                        --build-number "$BUILD_NUMBER" \\
                        --result SUCCESS
                '''
            }
        }

        stage('Archive metrics.csv and pipeline-results.log') {
            steps {
                archiveArtifacts artifacts: 'metrics.csv,pipeline-results.log', fingerprint: true
            }
        }
    }

    post {
        unsuccessful {
            sh '''
                set -eu
                if [ -f scripts/collect_metrics.py ]; then
                    build_time=0
                    test_time=0
                    if [ -n "${CI_PIPELINE_START:-}" ]; then
                        build_time=$(( $(date +%s) - CI_PIPELINE_START ))
                    fi
                    if [ -f "$WORKSPACE/.ci-test-time" ]; then
                        test_time=$(cat "$WORKSPACE/.ci-test-time")
                    fi
                    python3 scripts/collect_metrics.py \\
                        --build-time "$build_time" \\
                        --test-time "$test_time" \\
                        --deploy-time 0 \\
                        --success 0 \\
                        --build-number "$BUILD_NUMBER" \\
                        --result FAILURE
                fi
            '''
            archiveArtifacts artifacts: 'metrics.csv,pipeline-results.log', allowEmptyArchive: true
        }
        cleanup {
            sh 'rm -f "$WORKSPACE/.ci-test-time"'
        }
    }
}