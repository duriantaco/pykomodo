Contributing
=============

We welcome pull requests! Follow these steps:

1. **Fork and Clone**  
   Fork the repo on GitHub, clone locally.

2. **Create a Branch**  
   .. code-block:: bash

      git checkout -b feature/my-awesome-feature

3. **Write Tests**  
   All new features require test coverage. We use `pytest`:

   .. code-block:: bash

      pytest tests/

   - Run tests locally to ensure they pass:

     .. code-block:: bash

        pytest tests/

4. **Submit a Pull Request**  
   Explain your changes, reference any issues. We use GitHub Actions to build the package 
   and run tests automatically.

Release Workflow
-----------------

When you push a tagged release, GitHub Actions builds and publishes the package:

- `.github/workflows/main.yml` handles building via `pip install build` and `twine upload`.
- Ensure you set your PyPI API token in the repository secrets.