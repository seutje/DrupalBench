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
    
    echo "Installing Drush 13..."
    docker-compose exec -T drupal bash -c "composer require drush/drush:^13 --no-interaction"
fi

echo "Installing Drupal site..."
docker-compose exec -T drupal ./vendor/bin/drush site:install \
  --db-url=mysql://drupal:drupal@db/drupal \
  --site-name="DrupalBench" \
  --account-name=admin \
  --account-pass=admin \
  -y

echo "Setting permissions..."
docker-compose exec -T drupal chown -R www-data:www-data web/sites web/modules web/themes

echo "Initializing git repository for benchmarking..."
docker-compose exec -T drupal git init
docker-compose exec -T drupal git config user.email "bench@example.com"
docker-compose exec -T drupal git config user.name "DrupalBench"
docker-compose exec -T drupal git add .
docker-compose exec -T drupal git commit -m "Initial Drupal 11 installation"

echo "Running Health Check..."
docker-compose exec -T drupal php /var/www/html/health-check.php

echo "Environment initialized successfully."
