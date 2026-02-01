<?php

namespace Drupal\my_module\Access;

use Drupal\Core\Access\AccessPolicyInterface;
use Drupal\Core\Session\AccountInterface;
use Drupal\Core\Access\AccessResult;

class BrokenAccessPolicy implements AccessPolicyInterface {

  public function calculatePermissions(AccountInterface $account, $scope) {
    // Logic here.
  }

  public function applies($scope) {
    return TRUE;
  }

}
