# Contributing

## Testing

### Unit tests

Unit tests can be run with,
```
pytest
```

These will use only synthetic data.

By default all tests, not in the following categories
are unit tests and run with the above command.


### Integration tests

Integrations tests can be run with,

```
pytest -m integration --icubam-config=<config.toml path>
```
This will detect the database in the dev section of the config file,
make a copy of it to a temporary location and provide a new config object
with the `integration_config` pytest fixture. It can be used as follows,

```py
@pytest.mark.integration
def test_some_integration(integration_config):
    db_path = integration_config.db.sqlite_path
```

If ``--icubam-config`` key is not provided, the above test would be skipped.
If ``-m integration`` option is not provided, both unit and integration tests
are run (see [pytest
documentation](https://docs.pytest.org/en/latest/usage.html#specifying-tests-selecting-tests)
for more details).


### Frontend tests

Frontend tests can be run in two ways,

 1. Manually starting the services with,
    ```
    python scripts/run_server.py --server=all --config=<..>
    ```
    and then running
    ```
    pytest --icubam-config=<..> frontend_tests/
    ```
    
 2. Letting pytest start the web-services automatically with,
    ```
    pytest --icubam-config=<..>  --run-server frontend_tests/
    ```
    which is equivalent to two above steps. Web-services will be stopped at
    the end of the test session.

## Code style

Install [pre-commit](https://pre-commit.com/#install) to
run code style checks before each commit:

```
$ pip install pre-commit
$ pre-commit install
```

These include, in particular, yapf, flake8 and mypy. pre-commit checks can be
disabled for a particular commit with `git commit -n`.
