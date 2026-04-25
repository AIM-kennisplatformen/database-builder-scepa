# How to integrate in your project

## Project setup (Pixi)

Pixi can use `pyproject.toml` as the project configuration file.

If you don’t already have a project, create one:

```bash
pixi init --format pyproject
```

There are two options of integrating database-builder-scepa into your project:

1. **Install directly from GitHub**
2. **Clone the repository locally and reference it from your project**

---

## Install directly from GitHub

This is the easiest way if you simply want to **use the library as a dependency**.

Add the dependency with:

```bash
pixi add "database-builder-scepa @ https://github.com/AIM-kennisplatformen/database-builder-scepa.git"
```

Pixi will:

- download the repository from GitHub
- install it into your environment
- manage it as a project dependency

No manual cloning is required.

## Install from a local clone (development)

If you want to **develop or test changes in the library**, clone the repository locally and reference the folder.

Clone the repository inside your project directory:

```bash
git clone https://github.com/AIM-kennisplatformen/database-builder-scepa.git
```

Your project structure might look like this:

```
my-project/
├─ pyproject.toml
├─ src/
├─ database-builder-scepa/
```

Add the following to your `pyproject.toml`:

```toml
  [tool.pixi.pypi-dependencies]
  database-builder-scepa = { path = "./database-builder-scepa", editable = true }
```

Using `editable = true` ensures that changes to the local library are immediately reflected in your environment.
