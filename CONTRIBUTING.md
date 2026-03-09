# Contributing to homelife.ai

Thank you for your interest in contributing to homelife.ai! This guide will help you get started.

## Getting Started

1. Fork the repository and clone your fork.
2. Follow the setup instructions in [getting-started.md](getting-started.md) to configure your development environment.
3. Create a new branch from `main` for your work.

## Branch Naming

Use the following prefixes for branch names:

- `feat/` — New features (e.g., `feat/audio-transcription`)
- `fix/` — Bug fixes (e.g., `fix/timeline-scroll`)
- `docs/` — Documentation changes (e.g., `docs/api-reference`)

## Commit Messages

Follow the conventional commit format:

- `feat:` — A new feature
- `fix:` — A bug fix
- `docs:` — Documentation only changes
- `refactor:` — Code change that neither fixes a bug nor adds a feature

Keep messages concise and descriptive. Example:

```
feat: add weekly activity trend analysis
fix: correct timezone offset in timeline view
```

## Pull Request Process

1. **Open an issue first** describing the problem or feature you want to address.
2. Reference the issue in your PR (e.g., "Closes #42").
3. Provide a clear description of your changes and the reasoning behind them.
4. Ensure all tests pass before requesting a review.
5. Keep PRs focused — one concern per pull request.

## Code Style

### Python

- Use type hints for function signatures.
- Prefer `dataclasses` for data structures.
- Use the `logging` module for output (not `print`).
- Follow standard Python naming conventions (snake_case for functions and variables, PascalCase for classes).

### TypeScript

- Enable strict mode.
- Use Hono for API routes and Vite for builds.
- Prefer explicit types over `any`.

## Testing

Please ensure all existing tests pass before submitting your PR. If you are adding new functionality, include tests where applicable.

## Questions?

If you have questions or need help, feel free to open an issue. We appreciate all contributions, whether it's fixing a typo, improving documentation, or building a new feature.
