# Contributing

You are considering to contribute. Thank you!
This document should get you up and running with your development environment.

## Development environment

1. Clone the repo: `git clone --recurse-submodules https://github.com/Cereal2nd/pyDuotecno`
2. (optional) To keep dependencies from different projects from conflicting,
   it's usually better to install every project in its own Virtual Environment.
   Start by creating a new virtualenv: `python3 -m venv duovenv`
   This will create a new directory called `duovenv`.
   You need to activate the virtual environment every time you open a new shell by running
   `source duovenv/bin/activate`.
   Your prompt will be prefixed with `(duovenv)` to indicate the virtual environment is active.

3. Install the development dependencies: `pip install -r requirements-dev.txt`

4. Prepare your changes

5. Run the tests to check if everything still works as expected: `pytest`

6. Run `pre-commit run --all-files` to check and correct formatting
