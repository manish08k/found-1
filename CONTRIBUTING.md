# Contribution Workflow

AutoFlow follows a fork-and-pull-request workflow.

## 1. Fork the Repository

Click the **Fork** button on GitHub to create your own copy of AutoFlow.

```text
github.com/manish08k/Autoflow
        ↓
github.com/yourusername/Autoflow
```

---

## 2. Clone Your Fork

```bash
git clone https://github.com/yourusername/Autoflow.git
cd Autoflow
```

---

## 3. Add the Original Repository as Upstream

This allows you to keep your fork updated.

```bash
git remote add upstream https://github.com/manish08k/Autoflow.git
```

Verify:

```bash
git remote -v
```

---

## 4. Create a Branch

Never work directly on `main`.

```bash
git checkout -b feature/github-integration
```

Examples:

```bash
feature/slack-node
feature/airtable-trigger
feature/workflow-editor

bugfix/oauth-refresh
bugfix/webhook-timeout

docs/readme-update
docs/api-guide
```

---

## 5. Make Changes

Implement your feature, fix bugs, add tests, or improve documentation.

---

## 6. Commit Changes

```bash
git add .
git commit -m "feat: add GitHub release node"
```

Examples:

```text
feat: add Airtable polling trigger
fix: resolve OAuth token refresh issue
docs: improve setup guide
refactor: optimize workflow executor
```

---

## 7. Push Your Branch

```bash
git push origin feature/github-integration
```

---

## 8. Open a Pull Request

Go to your fork on GitHub.

Click:

```text
Compare & Pull Request
```

Provide:

* Summary of changes
* Related issue
* Testing performed
* Screenshots (if UI changes)

---

## 9. Code Review

Project maintainers may:

* Request changes
* Ask questions
* Suggest improvements

Please respond constructively and update your branch as needed.

---

## 10. Merge

Once approved, a maintainer will merge the Pull Request into the main repository.

Your contribution will automatically appear in GitHub's Contributors section.

---

## Keeping Your Fork Updated

Fetch latest changes:

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

---

## First-Time Contributors

Look for issues labeled:

* good first issue
* help wanted
* documentation
* enhancement

These are recommended starting points for new contributors.

---

## Pull Request Checklist

Before submitting a PR:

* [ ] Code builds successfully
* [ ] Tests pass
* [ ] Documentation updated
* [ ] No unnecessary files committed
* [ ] Branch is up to date
* [ ] PR description completed

Thank you for contributing to AutoFlow.
