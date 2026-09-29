# Windows release support for 2.5.1

- Add Windows x64 wheel builds for CPython 3.10–3.14 in `.github/workflows/release.yml` using isolated uv builds.
- Require Windows builds and artifacts before publishing Linux wheels, Windows wheels, and the source distribution together.
- Run installation smoke checks on Linux and Windows using portable commands and the selected Python interpreter.
- Set `navconfig/version.py` to 2.5.1.
- Validate YAML, release artifact handling, shell syntax, and version metadata locally; native Windows compilation requires GitHub Actions.

Assumptions: Windows support targets x64 and the same standard CPython versions as Linux. No new package dependencies are needed. No CONTEXT.md is present.
