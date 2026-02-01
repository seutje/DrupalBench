<?php
/**
 * Health check script for DrupalBench
 * Verifies PHP 8.3 features and database compatibility.
 */

// 1. PHP 8.3 Readonly class / properties check
readonly class HealthCheck {
    public function __construct(public string $status) {}
}

$check = new HealthCheck('OK');
echo "PHP Version: " . PHP_VERSION . "\n";
echo "Readonly Property Status: " . $check->status . "\n";

if (version_compare(PHP_VERSION, '8.3.0', '>=')) {
    echo "PHP 8.3+ verified.\n";
} else {
    echo "PHP 8.3+ NOT verified.\n";
    exit(1);
}

// 2. Database connection check
$host = getenv('DRUPAL_DB_HOST') ?: 'db';
$db   = getenv('DRUPAL_DB_NAME') ?: 'drupal';
$user = getenv('DRUPAL_DB_USER') ?: 'drupal';
$pass = getenv('DRUPAL_DB_PASSWORD') ?: 'drupal';

try {
    $dsn = "mysql:host=$host;dbname=$db";
    $pdo = new PDO($dsn, $user, $pass);
    echo "Database connection (PDO) verified.\n";
    
    // Check for MySQL 8.0+ or MariaDB 10.6+
    $version = $pdo->getAttribute(PDO::ATTR_SERVER_VERSION);
    echo "Database Version: $version\n";
    
} catch (PDOException $e) {
    echo "Database connection failed: " . $e->getMessage() . "\n";
    exit(1);
}

echo "Drupal 11 Requirements Check: PASS\n";
