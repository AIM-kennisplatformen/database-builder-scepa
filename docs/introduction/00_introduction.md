# Introduction

Database-builder-scepa is a Python library that provides components for building data ingestion and retrieval pipelines for knowledge graph–oriented applications.

The library focuses on reusable building blocks for:

- Connecting to and interacting with external data sources
- Synchronizing data between systems
- Transforming and preparing data for storage in graph-based or structured databases
- Supporting document processing workflows for retrieval and embedding-based systems

It is not a standalone application, but a set of utilities intended to be composed into larger systems that manage structured and unstructured data in a consistent pipeline.

## Key features

- Modular components for building data ingestion and processing pipelines
- Connectors for integrating external data sources
- Synchronization mechanisms for maintaining consistency across data systems
- Utilities for transforming and normalizing structured and unstructured data
- Support for document preparation for embedding and retrieval workflows
- Cross-platform support (Windows, macOS, Linux)
- Python-based implementation using the [pixi](https://prefix.dev) package manager

## Requirements

The library can run on most modern systems. Minimum requirements:

- Windows (amd64), macOS Sequoia or later (ARM64), or Linux (amd64)
- 4 GB of RAM
- CPU with SIMD support (AVX2 on x86_64 or NEON on ARM64)

## License

Database-builder-scepa is licensed under the [Apache-2.0](https://github.com/AIM-kennisplatformen/database-builder-scepa/blob/main/LICENSE) license. This allows use in both open-source and commercial projects.

The project is developed as part of a research initiative at HAN University of Applied Sciences by students and lecturers.
