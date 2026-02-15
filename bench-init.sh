#!/bin/bash
set -e

echo "Starting DrupalBench Phase 1: Environment Orchestration..."

# Ensure the app directory exists
mkdir -p app

# Start the containers
docker-compose up -d

echo "Waiting for database to be ready..."
sleep 10

echo "Setting up Drupal 11 Environment..."
if [ -f "app/composer.json" ]; then
    echo "Using existing composer.json, running install..."
    docker-compose exec -T drupal bash -c "composer install --no-interaction"
else
    echo "Installing Drupal 11 Lean Core..."
    # Move health-check aside to allow composer to install in an empty directory
    mv app/health-check.php health-check.php.tmp
    docker-compose exec -T drupal bash -c "composer create-project drupal/recommended-project:^11 . --no-interaction"
    mv health-check.php.tmp app/health-check.php
    
    echo "Installing Drush 13 and Dev Dependencies..."
    docker-compose exec -T drupal bash -c "composer require drush/drush:^13 drupal/core-dev:^11 phpstan/phpstan mglaman/phpstan-drupal drupal/coder --dev -W --no-interaction"
fi

echo "Resetting Drupal database tables..."
docker-compose exec -T drupal mariadb --skip-ssl -udrupal -pdrupal -h db drupal <<'SQL'
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
docker-compose exec -T drupal ./vendor/bin/drush site:install \
  --db-url=mysql://drupal:drupal@db/drupal \
  --site-name="DrupalBench" \
  --account-name=admin \
  --account-pass=admin \
  -y

echo "Setting permissions..."
docker-compose exec -T drupal chown -R www-data:www-data web/sites web/modules web/themes

echo "Configuring PHPUnit..."
docker-compose exec -T drupal bash -c "cp web/core/phpunit.xml.dist web/core/phpunit.xml"
docker-compose exec -T drupal bash -c "sed -i 's|name=\"SIMPLETEST_DB\" value=\"\"|name=\"SIMPLETEST_DB\" value=\"mysql://drupal:drupal@db/drupal\"|' web/core/phpunit.xml"
docker-compose exec -T drupal bash -c "sed -i 's|name=\"SIMPLETEST_BASE_URL\" value=\"\"|name=\"SIMPLETEST_BASE_URL\" value=\"http://localhost\"|' web/core/phpunit.xml"
docker-compose exec -T drupal bash -c "mkdir -p web/sites/simpletest/browser_output && chown -R www-data:www-data web/sites/simpletest"

echo "Initializing git repository for benchmarking..."
docker-compose exec -T drupal git init
docker-compose exec -T drupal git config user.email "bench@example.com"
docker-compose exec -T drupal git config user.name "DrupalBench"
docker-compose exec -T drupal bash -c "git add . && if ! git diff --cached --quiet; then git commit -m 'Initial Drupal 11 installation'; else echo 'No changes to commit.'; fi"

echo "Running Health Check..."
docker-compose exec -T drupal php /var/www/html/health-check.php

echo "Environment initialized successfully."
