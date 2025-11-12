# Compatibility tools for Rattler Build

This repository contains a set of tools to help with the integration of rattler-build into conda-forge.
Mainly by providing an interface that is recognizable for uses used to `conda-build`

## Releasing rattler-build-conda-compat

1. update version in `pyproject.toml`
2. run `pixi update rattler-build-conda-compat`
3. open and merge PR with changes to pyproject.toml and pixi.lock
4. Create a new release at https://github.com/conda-forge/rattler-build-conda-compat/releases/new with
   - tag: vX.Y.Z
   - title: vX.Y.Z
   - Generate release notes
   - click Publish Release
