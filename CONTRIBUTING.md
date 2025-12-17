# Contributing to Healthcare Payment Integrity

## Development Workflow

We use a PR-based workflow with CI/CD checks. Direct pushes to `main`/`master` should be avoided.

### Branch Strategy

1. **Create a feature branch** from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Branch naming conventions**:
   - `feature/` - New features
   - `fix/` - Bug fixes
   - `refactor/` - Code refactoring
   - `docs/` - Documentation updates
   - `test/` - Test additions/updates

### Making Changes

1. Make your changes on the feature branch
2. Run tests locally before pushing:
   ```bash
   # Run unit tests
   PYTHONPATH=backend pytest tests/ -v

   # Run linting
   pip install ruff
   ruff check backend/ scripts/
   ruff format --check backend/ scripts/
   ```

3. Commit with meaningful messages:
   ```bash
   git add .
   git commit -m "feat: add new validation rule for duplicate claims"
   ```

### Creating a Pull Request

1. Push your branch:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Open a PR on GitHub targeting `main`

3. Fill out the PR template with:
   - Summary of changes
   - Type of change
   - Testing performed
   - Related issues

4. Wait for CI checks to pass:
   - Linting (Ruff)
   - Unit tests (pytest)
   - Type checking (mypy) - advisory
   - Security scan (bandit) - advisory

5. Request review if needed

6. Merge after approval and passing CI

### CI/CD Pipeline

The following checks run automatically on PRs:

| Check | Tool | Status |
|-------|------|--------|
| Linting | Ruff | Required |
| Tests | pytest | Required |
| Type Check | mypy | Advisory |
| Security | bandit | Advisory |

### Local Development Setup

```bash
# Install dependencies
pip install -r backend/requirements.txt
pip install -r requirements-dev.txt

# Run the backend
make run

# Run tests
PYTHONPATH=backend pytest tests/ -v

# Download CMS data
make data-all
```

### Code Style

- Python code follows PEP 8 (enforced by Ruff)
- Use type hints where practical
- Keep functions focused and testable
- Add tests for new functionality

### Commit Message Format

Use conventional commit format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `test:` - Test changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

Example: `feat: add NCCI MUE validation for unit limits`
