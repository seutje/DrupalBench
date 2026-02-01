<?php

namespace Drupal\Tests\my_module\Unit;

use Drupal\Tests\UnitTestCase;

/**
 * @group my_module
 */
class BrokenTest extends UnitTestCase {

  /**
   * @dataProvider providerTestData
   */
  public function testSomething($data) {
    $this->expectError();
    $this->assertTrue(TRUE);
  }

  public function providerTestData() {
    return [
      ['data1'],
    ];
  }

}

/**
 * @Block(
 *   id = "broken_block",
 *   admin_label = @Translation("Broken Block"),
 * )
 */
class BrokenBlock {}
