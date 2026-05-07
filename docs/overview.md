## Database Builder SCEPA

Database Builder SCEPA is a Python application for building data ingestion and retrieval pipelines for knowledge graph–oriented systems.

It provides a concrete pipeline (`src/scepa_app/main.py`) plus reusable components for:

- Connecting to external sources (Zotero, PDF sources)
- Synchronizing sources and tracking deltas
- Normalizing metadata for storage
- Storing vectors in Qdrant and graph nodes in TypeDB

## Project setup (Pixi)

Pixi uses `pyproject.toml` as the project manifest.

```bash
pixi init --format pyproject
```

### Install directly from GitHub

```bash
pixi add "database-builder-scepa @ https://github.com/AIM-kennisplatformen/database-builder-scepa.git"
```

### Install from a local clone (development)

```bash
git clone https://github.com/AIM-kennisplatformen/database-builder-scepa.git
```

```toml
[tool.pixi.pypi-dependencies]
database-builder-scepa = { path = "./database-builder-scepa", editable = true }
```

## Repository layout

```
.
├── docs
├── LICENSE
├── mkdocs.yml
├── pixi.lock
├── pyproject.toml
├── README.md
├── src
└── tests
```

## Branches

The main development branch is `main`.
Feature branches follow `xx-<feature_name>` for planned work and `<feature_name>` for hotfixes.

## FAQ

### Where can I ask questions?

Use [GitHub issues](https://github.com/AIM-kennisplatformen/database-builder-scepa/issues) for application-related questions and bug reports.

### Is GPU/NPU supported?

GPU/NPU support depends on Docling and your LLM runtime. If Docling and your OpenAI-compatible runtime support your hardware, the pipeline will too.

### Why use Pixi instead of UV?

Pixi is the reference environment because it resolves Python and system dependencies together. UV is supported for a pure-Python subset, but Pixi provides the reproducible, multi-platform setup the app needs.

## Contributing

Rules:

- Changes go through a pull request with at least one review.
- Discuss dependency changes in `pyproject.toml` before submitting.
- Large refactors should be agreed on before the PR.

Developer commands:

```bash
pixi run test
pixi run lint
pixi run typecheck
```
