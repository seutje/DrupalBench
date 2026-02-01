This plan outlines the systematic construction of **DrupalBench**, a benchmarking suite designed to evaluate LLMs on modern Drupal 11 engineering standards. Each phase is structured to be executed with AI assistance, focusing on modularity and rigorous human verification.

---

## **Phase 1: Environment Orchestration & System Requirements**

The goal is to establish the "clean slate" Drupal 11 environment. Because Drupal 11 has strict requirements (PHP 8.3, modern SQL drivers), this phase ensures the testing ground is technically accurate.

* **Task 1.1:** Develop a `docker-compose.yml` and `Dockerfile` stack mimicking the Drupal 11 minimum requirements.
* **Task 1.2:** Automate the installation of Composer 2.7.0+ and Drush 13 within the container.
* **Task 1.3:** Create a health-check script that verifies PHP 8.3 features (e.g., readonly properties) and database compatibility.

> **Deliverable:** A functional, containerized environment that successfully bootstraps a "Lean Core" Drupal 11 installation.
> **Verification:** A human runs `./bench-init.sh` and confirms the system report shows PHP 8.3.x and Drupal 11.0.x active.

---

## **Phase 2: Data Mining & Task Curation (The "SWE-bench" Layer)**

This phase focuses on extracting real-world challenges from the Drupal.org ecosystem to ensure the benchmark isn't purely theoretical.

* **Task 2.1:** Script a scraper for the Drupal.org REST API to identify issues tagged "Drupal 11.x" and "RTBC" (Reviewed and Tested by the Community).
* **Task 2.2:** Filter issues to ensure they include a Merge Request (MR) with existing PHPUnit tests.
* **Task 2.3:** Map "Issue Descriptions" to input prompts and "Committed Patches" to ground truth.

> **Deliverable:** A `tasks.json` dataset containing 100+ validated issue pairs with associated core/module versions.
> **Verification:** A human reviews 5 random entries in the JSON to ensure the "prompt" provides enough context to solve the problem described in the "patch."

---

## **Phase 3: Domain-Specific Test Implementation**

DrupalBench requires specific modules to evaluate the four architectural pillars. This phase builds the "evaluation harness" for each logic type.

### **Domain Matrix**

| Domain | Focus Area | Verification Method |
| --- | --- | --- |
| **I: Backend** | PHP 8.3 Refactoring & PHPUnit 10 | Static analysis of attributes vs. annotations. |
| **II: Frontend** | Single Directory Components (SDC) | Directory structure and `component.yml` validation. |
| **III: Recipes** | Recipes API & Config Actions | Idempotency check (applying the recipe twice). |
| **IV: Security** | Access Policy API | Cache context verification in `calculatePermissions`. |

* **Task 3.1:** Write "Evaluation Wrappers" for each domain that verify specific Drupal 11 syntax (e.g., checking for `#` attributes instead of `@` annotations).

> **Deliverable:** A suite of four "Domain Validators" scripts.
> **Verification:** A human manually injects a "broken" patch (e.g., using a Drupal 10 legacy hook) and confirms the Backend Validator flags it.

---

## **Phase 4: Scoring Pipeline & Statistical Rigor**

This phase implements the mathematical evaluation of LLM performance, specifically the probabilistic nature of code generation.

* **Task 4.1:** Implement the  metric to evaluate  samples per task.
* **Task 4.2:** Integrate `phpcs` with the `DrupalPractice` ruleset and `phpstan-drupal` at Level 5.
* **Task 4.3:** Create a reporting engine that generates a Markdown summary of the model's performance.

> **Deliverable:** A `scoring_engine.py` script that outputs a finalized PDF/Markdown report for any evaluated LLM.
> **Verification:** A human runs the engine on a dummy "test run" and verifies that the  math aligns with the number of passing containers.

---

## **Phase 5: Synthetic Task Generation (Scaling)**

To prevent benchmark saturation, we need the ability to generate new, verified tasks using high-capacity models (e.g., GPT-4o or Claude 3.5 Sonnet).

* **Task 5.1:** Create a "Task Generator" prompt that uses Drupal 11 Change Records to invent new SDC or Access Policy challenges.
* **Task 5.2:** Build a "Self-Correction" loop: the LLM generates a task, the Docker harness tests it; if it fails to install, the task is discarded.

> **Deliverable:** A library of 500+ functionally verified synthetic tasks.
> **Verification:** A human attempts to solve 3 synthetic tasks manually to ensure the instructions are logical and the "passing" state is achievable.
