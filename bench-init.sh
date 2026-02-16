#!/bin/bash
set -e

echo "Starting DrupalBench Phase 1: Environment Orchestration..."

# Ensure the app directory exists
mkdir -p app

DRUPALBENCH_EXEC_TIMEOUT_SEC="${DRUPALBENCH_EXEC_TIMEOUT_SEC:-900}"
DRUPALBENCH_PROBE_TIMEOUT_SEC="${DRUPALBENCH_PROBE_TIMEOUT_SEC:-20}"

# Ensure compose service containers are in a runnable state before exec calls.
ensure_service_runnable() {
    local service="$1"
    local container_id
    local paused
    local status

    container_id="$(docker compose ps -q "$service")"
    if [ -z "$container_id" ]; then
        return
    fi

    paused="$(docker inspect -f '{{.State.Paused}}' "$container_id" 2>/dev/null || echo false)"
    status="$(docker inspect -f '{{.State.Status}}' "$container_id" 2>/dev/null || echo unknown)"

    if [ "$paused" = "true" ]; then
        echo "Service '$service' is paused. Restarting container..."
        if ! timeout --signal=KILL --kill-after=5s 20 docker restart "$container_id" >/dev/null 2>&1; then
            echo "Restart failed; attempting to unpause '$service' instead..."
            docker unpause "$container_id" >/dev/null 2>&1 || docker compose unpause "$service" >/dev/null 2>&1 || true
        fi
    fi

    case "$status" in
        exited|created|dead)
            echo "Service '$service' is $status. Starting container..."
            docker start "$container_id" >/dev/null 2>&1 || docker compose start "$service" >/dev/null 2>&1 || true
            ;;
    esac
}

compose_exec_drupal() {
    local err_file
    local rc

    ensure_service_runnable drupal
    if ! probe_drupal_exec; then
        docker compose unpause drupal >/dev/null 2>&1 || true
        ensure_service_runnable drupal
        if ! probe_drupal_exec; then
            echo "Drupal container is not accepting exec commands. On WSL2 + Docker Desktop, restart Docker Desktop and rerun bench-init.sh." >&2
            return 1
        fi
    fi

    err_file="$(mktemp)"
    # Composer and Drush often emit progress on stderr; mirror it live so long
    # operations do not appear stuck while still keeping a copy for diagnostics.
    if timeout --signal=KILL --kill-after=10s "$DRUPALBENCH_EXEC_TIMEOUT_SEC" docker compose exec -T drupal "$@" 2> >(tee "$err_file" >&2); then
        rm -f "$err_file"
        return 0
    fi

    rc=$?
    if [ -s "$err_file" ]; then
        cat "$err_file" >&2
    fi
    if grep -qi "cannot exec in a paused container" "$err_file"; then
        echo "Drupal container reported paused during exec. Restarting and retrying once..." >&2
        timeout --signal=KILL --kill-after=5s 20 docker restart "$(docker compose ps -q drupal)" >/dev/null 2>&1 || docker compose unpause drupal >/dev/null 2>&1 || true
        ensure_service_runnable drupal
        rm -f "$err_file"
        timeout --signal=KILL --kill-after=10s "$DRUPALBENCH_EXEC_TIMEOUT_SEC" docker compose exec -T drupal "$@"
        return $?
    fi

    if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        rm -f "$err_file"
        echo "Drupal exec timed out after ${DRUPALBENCH_EXEC_TIMEOUT_SEC}s. On WSL2 + Docker Desktop, restart Docker Desktop and rerun bench-init.sh." >&2
        return 1
    fi

    rm -f "$err_file"
    return $rc
}

probe_drupal_exec() {
    local probe_output
    local rc

    if probe_output="$(timeout --signal=KILL --kill-after=5s "$DRUPALBENCH_PROBE_TIMEOUT_SEC" docker compose exec -T drupal bash -lc "true" 2>&1)"; then
        return 0
    fi

    rc=$?
    if [ "$rc" -eq 124 ] || printf "%s" "$probe_output" | grep -qi "cannot exec in a paused container"; then
        return 1
    fi

    printf "%s\n" "$probe_output" >&2
    return "$rc"
}

# Start the containers
docker compose up -d
ensure_service_runnable drupal
ensure_service_runnable db

echo "Waiting for database to be ready..."
sleep 10

echo "Setting up Drupal 11 Environment..."
if [ -f "app/composer.json" ]; then
    echo "Using existing composer.json, running install..."
    compose_exec_drupal bash -c "composer install --no-interaction"
else
    echo "Installing Drupal 11 Lean Core..."
    # Move health-check aside to allow composer to install in an empty directory
    mv app/health-check.php health-check.php.tmp
    compose_exec_drupal bash -c "composer create-project drupal/recommended-project:^11 . --no-interaction"
    mv health-check.php.tmp app/health-check.php
    
    echo "Installing Drush 13 and Dev Dependencies..."
    compose_exec_drupal bash -c "composer require drush/drush:^13 drupal/core-dev:^11 phpstan/phpstan mglaman/phpstan-drupal drupal/coder --dev -W --no-interaction"
fi

echo "Resetting Drupal database tables..."
compose_exec_drupal mariadb --skip-ssl -udrupal -pdrupal -h db drupal <<'SQL'
SET SESSION group_concat_max_len = 1000000;
SET FOREIGN_KEY_CHECKS = 0;
SELECT GROUP_CONCAT(CONCAT('`', table_name, '`')) INTO @tables
FROM information_schema.tables
WHERE table_schema = DATABASE();
SET @drop_stmt = IF(@tables IS NULL, 'SELECT 1', CONCAT('DROP TABLE ', @tables));
PREPARE stmt FROM @drop_stmt;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
SET FOREIGN_KEY_CHECKS = 1;
SQL

echo "Installing Drupal site..."
compose_exec_drupal ./vendor/bin/drush site:install \
  --db-url=mysql://drupal:drupal@db/drupal \
  --site-name="DrupalBench" \
  --account-name=admin \
  --account-pass=admin \
  -y

echo "Setting permissions..."
compose_exec_drupal chown -R www-data:www-data web/sites web/modules web/themes

echo "Configuring PHPUnit..."
compose_exec_drupal bash -c "cp web/core/phpunit.xml.dist web/core/phpunit.xml"
compose_exec_drupal bash -c "sed -i 's|name=\"SIMPLETEST_DB\" value=\"\"|name=\"SIMPLETEST_DB\" value=\"mysql://drupal:drupal@db/drupal\"|' web/core/phpunit.xml"
compose_exec_drupal bash -c "sed -i 's|name=\"SIMPLETEST_BASE_URL\" value=\"\"|name=\"SIMPLETEST_BASE_URL\" value=\"http://localhost\"|' web/core/phpunit.xml"
compose_exec_drupal bash -c "mkdir -p web/sites/simpletest/browser_output && chown -R www-data:www-data web/sites/simpletest"

echo "Initializing git repository for benchmarking..."
compose_exec_drupal git init
compose_exec_drupal git config user.email "bench@example.com"
compose_exec_drupal git config user.name "DrupalBench"
compose_exec_drupal bash -c "git add . && if ! git diff --cached --quiet; then git commit -m 'Initial Drupal 11 installation'; else echo 'No changes to commit.'; fi"

echo "Running Health Check..."
compose_exec_drupal php /var/www/html/health-check.php

echo "Environment initialized successfully."
