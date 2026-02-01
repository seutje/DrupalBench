# **Architectural Design and Empirical Framework for DrupalBench: A Specialized Large Language Model Benchmark for Drupal 11 Engineering**

The rapid evolution of Artificial Intelligence within the software engineering domain has necessitated the development of increasingly sophisticated evaluative frameworks. While general-purpose benchmarks have historically sufficed for assessing basic algorithmic proficiency, the emergence of complex, framework-specific ecosystems like Drupal 11 demands a more nuanced approach. The proposed "DrupalBench" framework represents a critical advancement in this trajectory, offering a specialized environment designed to measure the capability of Large Language Models (LLMs) to navigate the unique architectural, procedural, and standards-based requirements of the Drupal 11 ecosystem. As the Drupal community moves toward a leaner core and an API-first methodology, the ability of AI agents to assist in complex migrations, site building via recipes, and security-hardened component development becomes a fundamental metric of their utility.1

## **Technical Evolution of the Drupal Core and the Benchmarking Gap**

The transition from Drupal 10 to Drupal 11 is not merely a version increment but a strategic pivot toward a streamlined, modern architecture. This shift involves the removal of significant legacy code and the adoption of the latest PHP standards, creating a "clean slate" that poses unique challenges for LLMs trained on older datasets.1 Most contemporary LLMs suffer from "knowledge cutoff" issues where their training data may heavily reflect Drupal 7, 8, or 9 patterns that are now entirely obsolete. DrupalBench addresses this by providing a targeted testbed that isolates Drupal 11-specific features and requirements.

### **Technical Specifications and Environmental Constraints**

A defining characteristic of Drupal 11 is its aggressive modernization of the technology stack. The mandatory shift to PHP 8.3 represents a significant hurdle for automated code generation, as it introduces syntax and features that require the model to understand context-dependent type safety and performance optimizations.6 The following table delineates the core technical requirements that DrupalBench must enforce within its evaluation harness to ensure the validity of generated patches.

| Component | Drupal 11 Minimum Requirement | Implications for LLM Code Generation |
| :---- | :---- | :---- |
| PHP Version | 8.3.x (with 8.4 support in 11.1) | Requires understanding of readonly properties, typed constants, and intersection types.4 |
| Symfony Framework | Version 7 | Models must navigate the breaking changes from Symfony 6, including event dispatching and service definitions.6 |
| Database Drivers | MySQL 8.0, MariaDB 10.6, PostgreSQL 16, SQLite 3.45 | Requires knowledge of modern SQL syntax and specific handling of JSON1 in SQLite.7 |
| Frontend Stack | jQuery 4, CKEditor 5, Twig 3.9+ | Shift away from legacy JavaScript patterns and toward modern, component-based rendering.6 |
| Project Management | Composer 2.7.0+, Drush 13 | Mandates sophisticated dependency resolution and command-line execution knowledge.7 |

The removal of technical debt is equally critical. Drupal 11 has transitioned several long-standing core modules—including Actions UI, Book, Tracker, Forum, Statistics, and Tour—to the contributed space.11 An LLM that attempts to solve a task by invoking the Forum module as part of the core will fail the DrupalBench evaluation, as it demonstrates an inability to distinguish between the current state of the core and historical implementations.15

### **The Limitations of General Code Benchmarks**

General-purpose benchmarks like HumanEval or MBPP focus on isolated, single-file programming tasks that often lack the structural complexity of a modern CMS.17 While a model might successfully write a recursive function in PHP, it may fail entirely to understand how to register that function as a service in Drupal 11, how to inject the @database service, or how to implement the necessary cache tags to ensure performance efficiency.19 DrupalBench shifts the focus from "coding" to "engineering," evaluating the model's ability to operate within a multi-file repository where configuration is managed via YAML, data is modeled via entities, and access is governed by dynamic policies.18

## **Architectural Pillars of the DrupalBench Framework**

To provide a comprehensive assessment of LLM performance, DrupalBench is structured around four primary domains of expertise: Backend Logic and API usage, Frontend Component Architecture, Site Building through Recipes and Config Actions, and Security/Access Control.

### **Domain I: Backend Logic and PHP 8.3 Refactoring**

The backend domain of DrupalBench targets the model's proficiency with the Drupal core API and the modern PHP 8.3 environment. A significant portion of the tasks in this domain involves refactoring legacy hooks into modern event subscribers or service-oriented architectures. The removal of deprecated APIs in Drupal 11 creates a strict environment where the model must not only generate new code but also identify and replace obsolete patterns in existing codebases.1

One critical area of focus is the PHPUnit 10 migration. Drupal 11 upgrades from PHPUnit 9.5 to 10.5, a transition that introduces numerous breaking changes, such as the requirement for static data providers and the removal of the Symfony PHPUnit-bridge.12 DrupalBench evaluates models on their ability to update test suites to these new standards. For instance, a model must be able to convert non-static @dataProvider methods into static methods and replace deprecated expectError() calls with modern attribute-based or exception-based testing patterns.23

### **Domain II: Single Directory Components (SDC) and Modern Theming**

The stabilization of Single Directory Components (SDC) in Drupal 11 core represents a paradigm shift in how user interfaces are constructed. SDC consolidates Twig, YAML, CSS, and JavaScript into a single directory, facilitating reusability and maintainability.26 DrupalBench includes tasks that require the generation of complete SDC directories, testing the model's ability to maintain consistency across these disparate file types.28

A key challenge in this domain is the correct implementation of the component.yml file, which defines the props and slots for the component. The benchmark evaluates whether the model correctly distinguishes between "Props" (scalar data like strings or integers) and "Slots" (placeholders for rendered content), a distinction critical for the functional integrity of the theme layer.30 Furthermore, the model must demonstrate the ability to embed these components using native Twig tools like the include, embed, and extends tags, ensuring that the generated frontend code is fully integrated into the Drupal render pipeline.31

### **Domain III: The Recipes API and Configuration Management**

The "Starshot" initiative and the introduction of the Recipes API in Drupal 11 aim to provide a low-code/no-code experience for site builders.1 However, the creation of these recipes requires deep technical knowledge of YAML-based configuration actions. DrupalBench evaluates LLMs on their ability to author recipes that automate module installation, permission granting, and configuration overrides.32

The benchmark tasks in this domain focus on "idempotent" configuration updates. A model is tasked with creating a recipe that can be applied to a site multiple times without causing errors or unexpected state changes.35 This requires the model to use the Config Actions API to call specific PHP methods on configuration objects, such as grantPermission on a user\_role entity.34 The following comparison highlights the shift from traditional installation profiles to the more granular Recipe system.

| Feature | Installation Profiles | Drupal 11 Recipes |
| :---- | :---- | :---- |
| Lifecycle | Fixed at site install; hard to change later. | Composable; can be applied at any time.2 |
| Scope | Monolithic; covers the entire site setup. | Atomic; targets specific features (e.g., SEO, Events).32 |
| Execution | Procedural PHP code in .install files. | Declarative YAML via Config Actions API.33 |
| Reusability | Low; often site-specific. | High; designed for cross-project standardization.39 |

### **Domain IV: Access Policy API and Dynamic Security**

Perhaps the most sophisticated addition to Drupal 11 is the Access Policy API, which transitions the framework from simple Role-Based Access Control (RBAC) to a more flexible Policy-Based Access Control (PBAC) model.22 DrupalBench includes advanced tasks that require the implementation of custom access policies, such as restricting access based on time of day, email domain, or taxonomic terms.42

A successful task completion in this domain requires the model to implement a service class that extends AccessPolicyBase and correctly overrides the calculatePermissions method.22 Crucially, the model must also define the correct cache contexts via getPersistentCacheContexts to ensure that permissions are updated when the underlying conditions change.44 Failure to include these cache contexts results in security vulnerabilities or performance degradation, both of which are flagged by the DrupalBench evaluation harness.22

## **Frontend Visualization and Comparative Analysis**

To facilitate the interpretation of benchmark results, DrupalBench includes a web-based dashboard built with Vite, React, and Tailwind CSS. This interface serves as the primary consumption layer for researchers and developers to compare model performance across the four architectural pillars.

### **Multi-Model Dashboard**

The dashboard provides a high-level overview of all models evaluated by the DrupalBench harness. It visualizes critical metrics such as pass@1 and pass@5, enabling a direct comparison of different LLM architectures and training methodologies. The use of Tailwind CSS ensures a responsive, "developer-centric" dark-themed aesthetic that aligns with modern engineering tools.

### **Granular Task Inspection**

For each model, the dashboard offers a detailed breakdown of performance on a task-by-task basis. This includes:
* **Functional Correctness:** Pass/fail status based on PHPUnit test execution.
* **Domain Validation:** Specific results from the Backend, Frontend (SDC), Recipes, and Security validators.
* **Code Quality Metrics:** Feedback from PHPCS and PHPStan analysis.

This level of granularity allows developers to identify specific failure modes—such as a model's tendency to use deprecated annotations instead of attributes—and adjust fine-tuning strategies accordingly.

## **Dataset Curation and Evaluation Harness Design**

The validity of DrupalBench rests on the quality of its task instances and the rigor of its execution environment. Following the "SWE-bench" model, DrupalBench utilizes real-world data from the Drupal community to ensure that the benchmark is not merely theoretical but reflects the actual work of software engineers.18

### **Leveraging the Drupal.org Ecosystem**

The Drupal.org issue queue and REST API provide a continuous stream of potential task instances. DrupalBench automates the extraction of these tasks by identifying issues that meet specific criteria:

1. **Branch Compatibility:** The issue must be tagged for Drupal 11.x or 12.x.49  
2. **Resolution Verification:** The issue must have a corresponding Merge Request (MR) that has been "Reviewed and Tested by the Community" (RTBC) and subsequently committed.47  
3. **Test Coverage:** The MR must include new or updated tests (Unit, Kernel, or Functional) that verify the fix.25

By using the issue description as the input "prompt" and the committed patch as the "ground truth," DrupalBench creates a high-fidelity evaluation set that tests the model's ability to resolve bugs and implement features in a real-world context.48

### **Docker-Based Execution and Reproducibility**

To prevent "hallucinated" successes, every patch generated by an LLM is executed within a containerized environment.53 The DrupalBench harness uses Docker to provision a full Drupal 11 stack, including the web server, database, and all Composer dependencies.10 This ensures that the code generated by the model actually runs and passes the associated tests.53

The evaluation process follows a strict sequence of stages to ensure consistency:

1. **Environment Setup:** Provisioning a Docker container with PHP 8.3 and the target Drupal 11 core version.54  
2. **Repository Cloning:** Cloning the specific version of the module or core where the issue exists.55  
3. **Patch Application:** Applying the LLM-generated patch to the codebase.47  
4. **Verification Run:** Executing phpunit for the relevant test group.  
5. **Static Analysis:** Running phpstan and phpcs to verify adherence to Drupal coding standards and type safety.60

## **Measuring Performance: Metrics and Statistical Rigor**

DrupalBench employs a multi-faceted scoring system that goes beyond simple "pass/fail" results. This allows for a more granular understanding of a model's strengths and weaknesses.

### **The pass@k Metric**

As LLM outputs are probabilistic, evaluating a single response is insufficient for understanding a model's true potential. DrupalBench adopts the pass@k metric, which calculates the probability that at least one of ![][image1] generated samples for a given task is correct.63 The metric is calculated using an unbiased estimator:

![][image2]  
where ![][image3] is the total number of samples generated, and ![][image4] is the number of samples that pass all tests.65 This metric is particularly useful for assessing how a model would perform in an interactive setting where a developer might review several AI-generated suggestions.63

### **Code Quality and Standards Compliance**

Functional correctness is the primary goal, but professional Drupal development also requires adherence to strict coding standards. DrupalBench integrates the Drupal and DrupalPractice rule sets for PHP\_CodeSniffer to evaluate the "cleanliness" of the generated code.61 Points are deducted for violations such as:

* Lines exceeding 80 characters (except in specific cases).68  
* Incorrect indentation (2 spaces, no tabs).68  
* Lack of Unix-style line endings.70  
* Improper Twig formatting, such as missing spaces around filters or function calls.72

Furthermore, the benchmark uses PHPStan to ensure that the generated code is free of static analysis errors. Models are expected to produce code that passes PHPStan at least at Level 5, ensuring that types are respected and variables are correctly initialized.60

## **Implementation Strategy for Future Fine-Tuning**

One of the primary use cases for DrupalBench is to serve as a test for future fine-tuned models. A model specifically trained on the Drupal 11 core codebase, change records, and API documentation is expected to significantly outperform general-purpose models like GPT-4o or Claude 3.5 Sonnet on this benchmark.

### **Knowledge Injection via Change Records**

A critical component of a fine-tuned model's training set should be the "Change Records" for Drupal core.49 These records provide the official narrative of how APIs have changed, why certain modules were removed, and what replacements are recommended.51 By training on these records, a model can learn the specific "evolutionary path" of the framework, allowing it to accurately refactor legacy code into Drupal 11-compliant structures.14

### **Synthetic Task Generation**

Given the relatively recent release of Drupal 11, the number of available real-world issue instances may be limited initially. To overcome this, the DrupalBench framework includes a "Synthetic Task Generator." This tool uses a high-capacity model to generate thousands of variations of common Drupal 11 tasks—such as creating an SDC component for a specific UI element or writing an access policy for a specific user role—which are then validated through the Docker-based evaluation harness.47 Only those tasks that are functionally verified are added to the fine-tuning dataset, ensuring a high signal-to-noise ratio.

## **Cognitive Challenges and LLM Performance Bottlenecks**

The development of DrupalBench reveals several recurring failure modes in current state-of-the-art models. These bottlenecks provide insight into the specific cognitive gaps that specialized Drupal models must bridge.

### **The "Stale Syntax" Problem**

Most LLMs struggle with the transition from PHP annotations (e.g., @ConfigEntityType) to PHP 8 attributes (e.g., \#). While Drupal 11 supports both in some areas, the core is rapidly moving toward attributes.36 A general model will frequently generate legacy annotations because they are more prevalent in its pre-training data. DrupalBench specifically tests for this "stale syntax" by penalizing the use of deprecated docblock-based metadata when an attribute-based alternative exists.12

### **Multi-File Consistency and Namespace Integrity**

Drupal's PSR-4 autoloading requires a strict mapping between file paths and PHP namespaces.71 General models often fail to correctly place a new service class within the src/ directory or fail to match the namespace in the .module file with the service definition in services.yml. DrupalBench's repository-level evaluation requires the model to edit multiple files simultaneously, testing its ability to maintain "namespace integrity" across the entire module structure.20

### **The Caching Complexity**

Drupal's caching system—specifically the nuances of cache tags, contexts, and max-age—is notoriously difficult for humans and AI alike.19 In the context of the Access Policy API, a model must understand that adding a permission is only half the battle; it must also declare the correct cache contexts to ensure that the permission is recalculated when the user's role or the current time changes.44 DrupalBench tasks involving the Access Policy API are designed to fail if the cache metadata is missing or incorrect, highlighting the model's inability to reason about the framework's performance and consistency layer.22

## **Conclusions and Strategic Roadmap**

The establishment of DrupalBench provides the Drupal community and AI researchers with a robust, standardized tool for measuring the evolution of AI-driven CMS engineering. By focusing on the specific architectural shifts of Drupal 11—such as the lean core, SDC, Recipes, and the Access Policy API—the benchmark ensures that LLMs are evaluated on their ability to produce modern, secure, and performant code rather than simply repeating legacy patterns.1

As the Starshot initiative progresses, the role of AI in site building will become increasingly central. Models that perform well on DrupalBench will be the primary candidates for integration into the Drupal CMS administrative interface, providing real-time assistance to site builders and developers.3 The future of Drupal development is inextricably linked to the quality of its AI assistants, and DrupalBench is the necessary instrument for ensuring that quality.

The roadmap for DrupalBench includes the integration of multimodal tasks—assessing a model's ability to generate SDC components from UI screenshots—and the continuous update of the task set via the Drupal.org REST API to ensure the benchmark remains "live" and immune to data contamination.50 Through this rigorous and evolving framework, the Drupal ecosystem can lead the way in establishing professional standards for AI-assisted software development in the open-source world.

#### **Works cited**

1. Drupal 11 Updates: Core Features and Improvements, accessed February 1, 2026, [https://www.unifiedinfotech.net/blog/drupal-11-updates-a-deep-dive-into-core-improvements/](https://www.unifiedinfotech.net/blog/drupal-11-updates-a-deep-dive-into-core-improvements/)  
2. Drupal 11 Released \- Key Features and Modernised Technology, accessed February 1, 2026, [https://drunomics.com/en/blog/drupal-11-released-key-features-and-modernised-technology-214](https://drunomics.com/en/blog/drupal-11-released-key-features-and-modernised-technology-214)  
3. What's New In Drupal 11? Everything You Need to Know, accessed February 1, 2026, [https://www.northern.co/blog/new-drupal11/](https://www.northern.co/blog/new-drupal11/)  
4. Drupal 11 — Release Date, Features, and What to Expect | by Droptica, accessed February 1, 2026, [https://medium.com/@droptica/drupal-11-release-date-features-and-what-to-expect-e9def890e577](https://medium.com/@droptica/drupal-11-release-date-features-and-what-to-expect-e9def890e577)  
5. Drupal 11: New features and benefits of the latest release, accessed February 1, 2026, [https://www.hintogroup.eu/en/blog/drupal-11-new-features-and-benefits-latest-release](https://www.hintogroup.eu/en/blog/drupal-11-new-features-and-benefits-latest-release)  
6. Drupal 11.0 will require PHP 8.3 and MySQL 8.0, accessed February 1, 2026, [https://www.drupal.org/about/core/blog/drupal-110-will-require-php-83-and-mysql-80](https://www.drupal.org/about/core/blog/drupal-110-will-require-php-83-and-mysql-80)  
7. Drupal 11 Development Progress: Updated System Requirements ..., accessed February 1, 2026, [https://www.thedroptimes.com/38527/drupal-11-development-progress-updated-system-requirements-announced](https://www.thedroptimes.com/38527/drupal-11-development-progress-updated-system-requirements-announced)  
8. Drupal 11 Hosting Requirements: The Complete Technical ..., accessed February 1, 2026, [https://pantheon.io/learning-center/drupal/hosting-requirements](https://pantheon.io/learning-center/drupal/hosting-requirements)  
9. Prepare for a Smooth Upgrade to Drupal 11 \- Acquia, accessed February 1, 2026, [https://www.acquia.com/blog/upgrade-to-drupal-11](https://www.acquia.com/blog/upgrade-to-drupal-11)  
10. Is your site ready for Drupal 11? \- Newpath Web, accessed February 1, 2026, [https://www.newpathweb.com.au/blog/is-your-website-ready-for-drupal-11/](https://www.newpathweb.com.au/blog/is-your-website-ready-for-drupal-11/)  
11. Drupal 11 – What Changes Does it Bring? \- Smartbees, accessed February 1, 2026, [https://smartbees.co/blog/drupal-11](https://smartbees.co/blog/drupal-11)  
12. drupal 11.0.0 | Drupal.org, accessed February 1, 2026, [https://www.drupal.org/project/drupal/releases/11.0.0](https://www.drupal.org/project/drupal/releases/11.0.0)  
13. Drupal 11 is at the doorstep \- bPekker.dev, accessed February 1, 2026, [https://bpekker.dev/drupal-11/](https://bpekker.dev/drupal-11/)  
14. Is it Time to Upgrade to Drupal 11? \- Pantheon.io, accessed February 1, 2026, [https://pantheon.io/learning-center/drupal/drupal-11](https://pantheon.io/learning-center/drupal/drupal-11)  
15. Deprecated and obsolete extensions | Core modules and themes, accessed February 1, 2026, [https://www.drupal.org/docs/core-modules-and-themes/deprecated-and-obsolete](https://www.drupal.org/docs/core-modules-and-themes/deprecated-and-obsolete)  
16. Upgrade to Drupal 11 Guide: Migrate from Drupal 10 or 7, accessed February 1, 2026, [https://drupfan.com/en/blog/ultimate-drupal-11-upgrade-guide-essential-steps-smooth-transition](https://drupfan.com/en/blog/ultimate-drupal-11-upgrade-guide-essential-steps-smooth-transition)  
17. SWE-bench Pro: Can AI Agents Solve Long-Horizon Software ..., accessed February 1, 2026, [https://static.scale.com/uploads/654197dc94d34f66c0f5184e/SWEAP\_Eval\_Scale%20(9).pdf](https://static.scale.com/uploads/654197dc94d34f66c0f5184e/SWEAP_Eval_Scale%20\(9\).pdf)  
18. Understanding LLM Code Benchmarks: From HumanEval to SWE ..., accessed February 1, 2026, [https://runloop.ai/blog/understanding-llm-code-benchmarks-from-humaneval-to-swe-bench](https://runloop.ai/blog/understanding-llm-code-benchmarks-from-humaneval-to-swe-bench)  
19. What's New in Drupal 11: The Latest Features and Enhancements, accessed February 1, 2026, [https://www.webeestudio.com/blog/whats-new-drupal-11-latest-features-and-enhancements](https://www.webeestudio.com/blog/whats-new-drupal-11-latest-features-and-enhancements)  
20. Extension for PHPStan to allow analysis of Drupal code. \- GitHub, accessed February 1, 2026, [https://github.com/mglaman/phpstan-drupal](https://github.com/mglaman/phpstan-drupal)  
21. Comprehensive Guide of Best Practices for Drupal Development, accessed February 1, 2026, [https://medium.com/@imma.infotech/comprehensive-guide-of-best-practices-for-drupal-development-e73d4ba64029](https://medium.com/@imma.infotech/comprehensive-guide-of-best-practices-for-drupal-development-e73d4ba64029)  
22. Drupal Access Policy demystified | SparkFabrik Tech Blog, accessed February 1, 2026, [https://tech.sparkfabrik.com/en/blog/drupal-access-policy-demystified/](https://tech.sparkfabrik.com/en/blog/drupal-access-policy-demystified/)  
23. \[meta\] Support PHPUnit 10 in Drupal 11 \[\#3217904\] | Drupal.org, accessed February 1, 2026, [https://www.drupal.org/project/drupal/issues/3217904](https://www.drupal.org/project/drupal/issues/3217904)  
24. Changes required for PHPUnit 10 compatibility | Drupal.org, accessed February 1, 2026, [https://www.drupal.org/node/3365413](https://www.drupal.org/node/3365413)  
25. Drupal 11 compatibility \[\#3446350\], accessed February 1, 2026, [https://www.drupal.org/project/updated/issues/3446350](https://www.drupal.org/project/updated/issues/3446350)  
26. Smarter Theming: Single Directory Components in Drupal, accessed February 1, 2026, [https://www.drupalhelps.com/tip/smarter-theming-single-directory-components-drupal](https://www.drupalhelps.com/tip/smarter-theming-single-directory-components-drupal)  
27. Single Directory Components (SDC) in Drupal 10 | ZANZARRA, accessed February 1, 2026, [https://zanzarra.com/blog/single-directory-components-sdc-drupal-10](https://zanzarra.com/blog/single-directory-components-sdc-drupal-10)  
28. Basic Concepts of Single Directory Component in Drupal, accessed February 1, 2026, [https://www.tothenew.com/blog/basic-concepts-of-single-directory-component-in-drupal/](https://www.tothenew.com/blog/basic-concepts-of-single-directory-component-in-drupal/)  
29. Single Directory Components | Drupal.org, accessed February 1, 2026, [https://www.drupal.org/project/sdc](https://www.drupal.org/project/sdc)  
30. Using Single-Directory Components | Theming Drupal | Drupal Wiki ..., accessed February 1, 2026, [https://www.drupal.org/docs/develop/theming-drupal/using-single-directory-components](https://www.drupal.org/docs/develop/theming-drupal/using-single-directory-components)  
31. Single Directory Components in Drupal Core \- Lullabot, accessed February 1, 2026, [https://www.lullabot.com/articles/getting-single-directory-components-drupal-core](https://www.lullabot.com/articles/getting-single-directory-components-drupal-core)  
32. Introduction to Drupal recipes \- QED42, accessed February 1, 2026, [https://www.qed42.com/insights/introduction-to-drupal-recipes](https://www.qed42.com/insights/introduction-to-drupal-recipes)  
33. Use Drupal's Config Actions API to Spice Up Your Recipes, accessed February 1, 2026, [https://www.thedroptimes.com/54771/use-drupals-config-actions-api-spice-your-recipes](https://www.thedroptimes.com/54771/use-drupals-config-actions-api-spice-your-recipes)  
34. Config Actions \- Drupal Recipes Initiative Documentation, accessed February 1, 2026, [https://project.pages.drupalcode.org/distributions\_recipes/config\_actions.html](https://project.pages.drupalcode.org/distributions_recipes/config_actions.html)  
35. Release Day: The Drupal Recipes API | Drupalize.Me, accessed February 1, 2026, [https://drupalize.me/blog/release-day-drupal-recipes-api](https://drupalize.me/blog/release-day-drupal-recipes-api)  
36. Config Action API \- Drupal API, accessed February 1, 2026, [https://api.drupal.org/api/drupal/core%21lib%21Drupal%21Core%21Config%21Action%21ConfigActionManager.php/group/config\_action\_api/11.x](https://api.drupal.org/api/drupal/core%21lib%21Drupal%21Core%21Config%21Action%21ConfigActionManager.php/group/config_action_api/11.x)  
37. Unlocking Drupal Recipes: Instantly Boost Your Website's Features, accessed February 1, 2026, [https://imagexmedia.com/blog/examples-how-drupal-recipes-work](https://imagexmedia.com/blog/examples-how-drupal-recipes-work)  
38. Overview \- Drupal Recipes Initiative Documentation, accessed February 1, 2026, [https://project.pages.drupalcode.org/distributions\_recipes/recipe.html](https://project.pages.drupalcode.org/distributions_recipes/recipe.html)  
39. Recipes: the new feature in Drupal 11 that revolutionizes content ..., accessed February 1, 2026, [https://direktpoint.com/blog/recipes-new-feature-drupal-11-revolutionizes-content-management](https://direktpoint.com/blog/recipes-new-feature-drupal-11-revolutionizes-content-management)  
40. The Ultimate List of Contributed Modules in Drupal CMS by ..., accessed February 1, 2026, [https://www.thedroptimes.com/47027/ultimate-list-contributed-modules-in-drupal-cms-functionality](https://www.thedroptimes.com/47027/ultimate-list-contributed-modules-in-drupal-cms-functionality)  
41. New access policy API | Drupal.org, accessed February 1, 2026, [https://www.drupal.org/node/3385551](https://www.drupal.org/node/3385551)  
42. Drupal 11 Features: What Makes It A Top Choice For Complex ..., accessed February 1, 2026, [https://hackmd.io/@x4jxZ3TSQi24SDLL09WN4w/r10pnW-8kg](https://hackmd.io/@x4jxZ3TSQi24SDLL09WN4w/r10pnW-8kg)  
43. Access Policy | Drupal.org, accessed February 1, 2026, [https://www.drupal.org/project/access\_policy](https://www.drupal.org/project/access_policy)  
44. Access Policy API \- bPekker.dev, accessed February 1, 2026, [https://bpekker.dev/access-policy-api/](https://bpekker.dev/access-policy-api/)  
45. Access policy API \- Drupal, accessed February 1, 2026, [https://www.drupal.org/docs/develop/drupal-apis/access-policy-api](https://www.drupal.org/docs/develop/drupal-apis/access-policy-api)  
46. The Power of Drupal 11: What's New & Improved \- Acquia, accessed February 1, 2026, [https://www.acquia.com/blog/the-power-of-drupal](https://www.acquia.com/blog/the-power-of-drupal)  
47. How We Collect SWE-Bench for Other Languages, accessed February 1, 2026, [https://fermatix.ai/SWE-Bench](https://fermatix.ai/SWE-Bench)  
48. Overview \- SWE-bench, accessed February 1, 2026, [https://www.swebench.com/SWE-bench/](https://www.swebench.com/SWE-bench/)  
49. Change records for Drupal core, accessed February 1, 2026, [https://www.drupal.org/list-changes/drupal](https://www.drupal.org/list-changes/drupal)  
50. REST and other APIs | APIs | Drupal.org guide on Drupal.org, accessed February 1, 2026, [https://www.drupal.org/drupalorg/docs/apis/rest-and-other-apis](https://www.drupal.org/drupalorg/docs/apis/rest-and-other-apis)  
51. Write a change record for a Drupal core issue, accessed February 1, 2026, [https://www.drupal.org/community/contributor-guide/task/write-a-change-record-for-a-drupal-core-issue](https://www.drupal.org/community/contributor-guide/task/write-a-change-record-for-a-drupal-core-issue)  
52. Running PHPUnit tests \- Drupal, accessed February 1, 2026, [https://www.drupal.org/docs/develop/automated-testing/phpunit-in-drupal/running-phpunit-tests](https://www.drupal.org/docs/develop/automated-testing/phpunit-in-drupal/running-phpunit-tests)  
53. SWE-bench Deep Dive: Redefining AI for Software Engineering, accessed February 1, 2026, [https://medium.com/@madhav\_mishra/swe-bench-deep-dive-redefining-ai-for-software-engineering-2898b1149b3d](https://medium.com/@madhav_mishra/swe-bench-deep-dive-redefining-ai-for-software-engineering-2898b1149b3d)  
54. Docker Setup Guide \- SWE-bench, accessed February 1, 2026, [https://www.swebench.com/SWE-bench/guides/docker\_setup/](https://www.swebench.com/SWE-bench/guides/docker_setup/)  
55. aorwall/SWE-bench-docker \- GitHub, accessed February 1, 2026, [https://github.com/aorwall/SWE-bench-docker](https://github.com/aorwall/SWE-bench-docker)  
56. Testing with drupalci for Docker Hub \- GitHub, accessed February 1, 2026, [https://github.com/marcelovani/drupalci](https://github.com/marcelovani/drupalci)  
57. Drupal contributed modules via Docker | by Kevin Wenger \- Medium, accessed February 1, 2026, [https://wengerk.medium.com/drupal-contributed-modules-via-docker-d643c8244177](https://wengerk.medium.com/drupal-contributed-modules-via-docker-d643c8244177)  
58. Docker containers to benchmark several php frameworks \- GitHub, accessed February 1, 2026, [https://github.com/bgeneto/php-frameworks-bench](https://github.com/bgeneto/php-frameworks-bench)  
59. How to run SWE-bench Verified in one hour on one machine, accessed February 1, 2026, [https://epoch.ai/blog/swebench-docker](https://epoch.ai/blog/swebench-docker)  
60. PHPStan in Drupal core, accessed February 1, 2026, [https://www.drupal.org/docs/develop/development-tools/phpstan/phpstan-in-drupal-core](https://www.drupal.org/docs/develop/development-tools/phpstan/phpstan-in-drupal-core)  
61. Check Standards/Practice Coding And Linting | Varbase Docs, accessed February 1, 2026, [https://docs.varbase.vardot.com/developers/extending-varbase/check-standards-practice-coding-and-linting](https://docs.varbase.vardot.com/developers/extending-varbase/check-standards-practice-coding-and-linting)  
62. Top PHP Static Code Analysis Tools for Drupal | Five Jars, accessed February 1, 2026, [https://fivejars.com/insights/top-php-static-code-analysis-tools-drupal/](https://fivejars.com/insights/top-php-static-code-analysis-tools-drupal/)  
63. Pass@k: A Practical Metric for Evaluating AI-Generated Code, accessed February 1, 2026, [https://medium.com/@ipshita/pass-k-a-practical-metric-for-evaluating-ai-generated-code-18462308afbd](https://medium.com/@ipshita/pass-k-a-practical-metric-for-evaluating-ai-generated-code-18462308afbd)  
64. Benchmarking and Revisiting Code Generation Assessment \- arXiv, accessed February 1, 2026, [https://arxiv.org/html/2505.06880v1](https://arxiv.org/html/2505.06880v1)  
65. I have Opinions on Pass@K \- You should too \- Runloop, accessed February 1, 2026, [https://runloop.ai/blog/i-have-opinions-on-pass-k-you-should-too](https://runloop.ai/blog/i-have-opinions-on-pass-k-you-should-too)  
66. Pass@$k$ Metric in Code Generation & RL \- Emergent Mind, accessed February 1, 2026, [https://www.emergentmind.com/topics/pass-k-metric-b5b58688-14e3-4ed9-b1f7-504db4b60803](https://www.emergentmind.com/topics/pass-k-metric-b5b58688-14e3-4ed9-b1f7-504db4b60803)  
67. HumanEval: A Benchmark for Evaluating LLM Code Generation ..., accessed February 1, 2026, [https://www.datacamp.com/tutorial/humaneval-benchmark-for-evaluating-llm-code-generation-capabilities](https://www.datacamp.com/tutorial/humaneval-benchmark-for-evaluating-llm-code-generation-capabilities)  
68. Drupal coding standards \- what are the best practices? \- Droptica, accessed February 1, 2026, [https://www.droptica.com/blog/what-are-drupal-coding-standards-and-how-use-them-your-daily-work/](https://www.droptica.com/blog/what-are-drupal-coding-standards-and-how-use-them-your-daily-work/)  
69. Configure PHPCS and PHPStan in DDEV for Drupal, accessed February 1, 2026, [https://eduardotelaya.com/blog/technology/2025-07-21-configure-phpcs-and-phpstan-in-ddev-for-drupal/](https://eduardotelaya.com/blog/technology/2025-07-21-configure-phpcs-and-phpstan-in-ddev-for-drupal/)  
70. Drupal Code Standards: Formatting \- Chromatic, accessed February 1, 2026, [https://chromatichq.com/insights/drupal-code-standards-formatting/](https://chromatichq.com/insights/drupal-code-standards-formatting/)  
71. PHP coding standards \- Drupal, accessed February 1, 2026, [https://project.pages.drupalcode.org/coding\_standards/php/coding/](https://project.pages.drupalcode.org/coding_standards/php/coding/)  
72. \[Obsolete\] Twig coding standards \- Drupal, accessed February 1, 2026, [https://www.drupal.org/docs/develop/coding-standards/twig-coding-standards](https://www.drupal.org/docs/develop/coding-standards/twig-coding-standards)  
73. Coding Standards \- Documentation \- Twig PHP \- Symfony, accessed February 1, 2026, [https://twig.symfony.com/doc/3.x/coding\_standards.html](https://twig.symfony.com/doc/3.x/coding_standards.html)  
74. Rule Levels \- PHPStan, accessed February 1, 2026, [https://phpstan.org/user-guide/rule-levels](https://phpstan.org/user-guide/rule-levels)  
75. Change records | Core change policies | About guide on Drupal.org, accessed February 1, 2026, [https://www.drupal.org/about/core/policies/core-change-policies/change-records](https://www.drupal.org/about/core/policies/core-change-policies/change-records)  
76. SWE-bench Goes Live\! \- arXiv, accessed February 1, 2026, [https://arxiv.org/html/2505.23419v2](https://arxiv.org/html/2505.23419v2)  
77. Creating a configuration entity type \- Drupal APIs, accessed February 1, 2026, [https://www.drupal.org/docs/drupal-apis/configuration-api/creating-a-configuration-entity-type](https://www.drupal.org/docs/drupal-apis/configuration-api/creating-a-configuration-entity-type)  
78. \[Obsolete\] Coding standards | Develop \- Drupal, accessed February 1, 2026, [https://www.drupal.org/docs/develop/standards](https://www.drupal.org/docs/develop/standards)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAXCAYAAADduLXGAAAAvElEQVR4XmNgGJRAGIh1gJgbXQId3AXiv0D8H4h50OSwggMMEMVEAZDCw+iC2ADIapDiaHQJbCCIAaJYEElsBhDPRuLDAch6mHv5gfg8EEsA8S8gVoIpggGQwtNALATEc6BiD6HiIM1wwAsV3AnEPcgS2MAkBoQTKqBsV4Q0KngOxG+R+CDFB6DsXAaI0+AAJAkyHZnfCmV/QhJnkGGASGoiiT0B4vlAHAnEwUjiDIwM2N3nBsSy6IKjAAYAQWIkupWfAyQAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA4CAYAAABAFaTtAAAFBklEQVR4Xu3dO4gdVRgH8BEjKIoPFCUYSQobH41YCdr5RFRQwUcaOxW0VewWRNRCEBGENMZCDRIE0cJKAoKItj4gKKhERESsFN96vswc7tmT2bt7N5vdObu/H3zMzDdzX9vsn3Pm0XUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAzDyX6kBR20X5m/Yt3wUA0JZvU12eavdQ20X+PU+nurbaBwDQlAhs59TNTfBK3ViH3+vGiCc7gQ0AaNxWBLabUu0Z1r9I9UKqI6n+ywfM8Vaq94rto8X6GIENAGjeVgS2Opi9Pyx/W9Y90ZupdqV6qurN+/4CGwDQvM0ObEupri+2r0h16bB+rOiPqYNe9kfdKAhsAEDzNjuw1aErPj/7qlgfE9OoH6S6q+rX71kS2ACA5m11YNsIP9eNgsAGADRvOwS2I3WjILABAM0T2AAAJk5gAwCYuKkGtm/qxhx/1Y2CwAYANG+qgS0ft39Zd9y89xTYAIBRf6a6cFg/O9VLxb7wddeHjI0OSqenejbV3lQfpbo51cFUb3crf9a8wPZP3dgAj6W6sW6OOJzq7m5+GMvchw0AWEienovwdGBYhlgvrSWIrEcOX3VIWSmUjQW277r+9afqO672vnFj3Qe71e/LFjzpAABYlzu7/pmXIUa7Lk51/2z38YCxWmhZrzqwHRmWpw3L2lhgC6fyO96Qal/dLMQIZIjPv7rcMeLLulER2ACgQUupPkz1cdePfpXPpYypzLO6fiqxDis5RPxY9PIx8TDzM1PtrvrZr8MyB4f4/Dg367xUV3b9526UHL5uSfVJqkPFvjFbEdhCHnk8GefXjRECGwA06NOuf8j4RcN2PMsy/qG/2/VhLivPO3st1QNdH7AeLfo5xOWpu7UGtti/r+vD4Rmpvh/6G6EeYau/S22zAlu812ZUTWADgEaV/9hfT3VJ1YtzqC4otiOo5UBQTi3mXn1yfkyH3jesx/E5sMUFCCG/Zi3naC2qDmyH844VrCewxehYhNOVakoENgBoVBlE8nrZyyNnj3R9yPph2H4+1R3DennuVPna3H986MfIXCzLUbT87MvoRzCKY2txlWkOhGN1zezQZerAlq0UvtYT2FoisAFAg2LEK67kjKnIGPmKacnwU6pzu37U61g3O7ftqlQPdf2oUh4pCznMvJNqT9EPcRuNJ4b1uOAgRtNeHbbj2JiGDfE5ce7bPcP2ycq39bi362/rEcuDqf7u+pHEMWOBLa4SjfPq4jfG+mY5WjcK8TeKkc5FCWwA0KCHU+2qmzvYWGDbCuW91N7o+qAc5w5+VvTXM+InsAFAg+Y9xmgnmkJgi1HOz4f1GOWM8wdvHbbLkHZd1994dxECGwA05vaun5KMqUJ6UwhscYuVclo5X6Eb09dLRT8sOsomsAEAzZtCYKtDWN6+rTvxhr/1sasR2ACA5k0xsM2z6JS2wAYANK+1wFZeqbsWAhsA0DyBDQBg4loLbIscGwQ2AKB5Uw1s+ekStbFj5xHYAIDmTSGwLXWz+65l+fFd+5d1XXQAAOxAUwhs4d9iPb5PBLW93fIRtZdTXVZsr4XABgA0byqB7cVu9lzXZ7r+EWKHZruPi2eyLkpgAwCaN5XAFvIVoHlULZb5UVS/DMtFCWwAQPOmFNhOBYENAGheBLYYycq1XZS/SWADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAkv8BvX8clDr1DZEAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAXCAYAAAA/ZK6/AAAAoUlEQVR4XmNgGAWDCdgB8V0gloHyhYH4BBTzwRTBgCwQzwJiGyD+D8QzgDgGKmcLFeOE8sFgKxBzALEfVDIYSU4SKmaMJMbgDaUPMEAkkQHMEB40cTAASbSiif0G4qtoYmCgxADRAKJhQBwqZgnlH0aSA5uM7pxJSGIgz0cgyTE8AeIHyAJAkAzE/xggwfoeTY5BnwEt6KBAgQESR6OAJAAAk+8dKpbFdh8AAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAZCAYAAAAMhW+1AAAAb0lEQVR4XmNgGAVkgXVA/B+I5wLxLyDOgUkwQiXmwASg/K8wzjMg/oeQY2BhgCjIAnFguq8iKQABYRjDjwGiwAUhhwoWMkAU8KBLwEArA0QBNhAIIjgZIApUUOUYzgNxEIwjwwBRBMMgSVaY5AgAAP77F8bmM5eqAAAAAElFTkSuQmCC>