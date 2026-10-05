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

        stage('Recommend RL Pipeline Strategy') {
            steps {
                sh '''
                    set -eu
                    rm -f recommendation.txt
                    .venv/bin/python rl/predict.py \\
                        --csv-path metrics_traditional.csv \\
                        --model-path rl_model.zip \\
                        --recommendation-file recommendation.txt \\
                        --seed "$BUILD_NUMBER"
                    test -s recommendation.txt
                '''
                script {
                    def selectedStrategy = readFile('recommendation.txt').trim()
                    def validStrategies = [
                        'Standard Pipeline',
                        'Enable Cache',
                        'Parallel Test Execution',
                        'Cache + Parallel Testing'
                        'Resource Optimized Mode',
                        'Security Scan',
                        'Fast Build Mode'
                    ]
                    if (!validStrategies.contains(selectedStrategy)) {
                        error("Invalid RL pipeline recommendation: ${selectedStrategy}")
                    }
                    echo "RL selected optimization strategy: ${selectedStrategy}"
                }
                archiveArtifacts artifacts: 'recommendation.txt', fingerprint: true
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

        stage('Archive pipeline artifacts') {
            steps {
                archiveArtifacts artifacts: 'metrics.csv,pipeline-results.log,recommendation.txt', fingerprint: true
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
            archiveArtifacts artifacts: 'metrics.csv,pipeline-results.log,recommendation.txt', allowEmptyArchive: true
        }
        cleanup {
            sh 'rm -f "$WORKSPACE/.ci-test-time"'
        }
    }
}