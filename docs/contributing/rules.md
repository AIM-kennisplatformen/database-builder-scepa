# How to contribute

Contributions are always welcome, this page gives a practical summary of the rules and development tools used for this library.

## Rules

The following rules are enforced for all developers of this library:

- Code must be merged through a pull request with at least one review. Branch rules enforce this and block pushes to `main`.
- Do not add or change dependencies in `pyproject.toml` without discussing it with the team leads. Python dependencies can be brittle and may break other parts of the project.
- It is fine to use Copilot to generate a pull request summary, but also add the reasoning behind key decisions manually.
- Discuss any refactors before opening a pull request. Large non-discussed refactors will be closed immediately.

## CI checks

We have the following checks:

- All Python tests should pass.
- All typecheck errors should be resolved.
- Code should be linted using Ruff.

## Developer commands

The Pixi config includes these convenience commands:

### Running unit-tests

```bash
pixi run test
```

### Running the linter

```bash
pixi run lint
```

### Running the type-checker

```bash
pixi run typecheck
```
