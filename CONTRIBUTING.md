# Contributing to Medibot

Thank you for considering contributing to **Medibot**! We welcome contributions of all kinds – bug reports, feature ideas, documentation improvements, and code contributions. Please follow the guidelines below to make the process smooth for everyone.

## Table of Contents
- [Getting Started](#getting-started)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Testing](#testing)
- [Issues & Bug Reports](#issues--bug-reports)
- [Documentation](#documentation)
- [License](#license)

## Getting Started
1. **Fork the repository** on GitHub.
2. **Clone your fork**:
   ```bash
   git clone https://github.com/<your-username>/Medibot.git
   cd Medibot
   ```
3. **Create a new branch** for your work:
   ```bash
   git checkout -b my-feature-branch
   ```
4. Install dependencies:
   ```bash
   # Backend (Python)
   pip install -r requirements.txt

   # Frontend (Node.js)
   cd frontend && npm install && cd ..
   ```
5. Ensure the project runs locally before making changes.

## Code Style
- **Python**: Follow PEP 8. Use `black` and `flake8` for formatting and linting.
- **JavaScript/TypeScript**: Follow the existing style; run `npm run lint`.
- Keep line length ≤ 100 characters where possible.
- Write clear, descriptive variable and function names.

## Submitting Changes
1. Make sure your changes are **self‑contained** and address a single concern.
2. Keep the repository clean – do not commit generated files (e.g., `node_modules/`, `__pycache__/`).
3. Run the test suite (see below) to ensure nothing is broken.
4. Push your branch to your fork:
   ```bash
   git push origin my-feature-branch
   ```
5. Open a **Pull Request** (PR) against the `main` branch of the upstream repository.

## Commit Messages
- Use the **imperative mood** (e.g., "Add login endpoint").
- Include a short summary line (≤ 50 characters) followed by a blank line and an optional detailed description.
- Reference related issues with `#<issue-number>`.

## Pull Request Process
- **Title**: Brief, descriptive title.
- **Description**: Explain *what* and *why* the change is needed. Include screenshots for UI changes.
- **Checklist**:
  - [ ] I have read the CONTRIBUTING guide.
  - [ ] My code follows the style guidelines.
  - [ ] I have added tests (if applicable).
  - [ ] All existing and new tests pass.
- Request review from at least one maintainer.

## Testing
- **Backend**: Run the pytest suite.
  ```bash
  pytest
  ```
- **Frontend**: Run the React/Next.js test runner (if configured) or manually verify UI changes.
- Ensure coverage does not decrease significantly.

## Issues & Bug Reports
- Search existing issues before opening a new one.
- Provide a clear title and description.
- Include steps to reproduce, expected behavior, and actual behavior.
- Attach logs or screenshots when helpful.

## Documentation
- Update `README.md` or relevant docs when adding features.
- Keep documentation in **Markdown** and follow the existing structure.
- Use proper headings and code blocks for readability.

## License
By contributing, you agree that your contributions will be licensed under the same MIT License as the project.

---

Thank you for helping make Medibot better! 🎉
