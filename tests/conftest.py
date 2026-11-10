"""Register the database test option before pytest parses arguments."""


def pytest_addoption(parser):
    parser.addoption(
        "--database-url",
        default="sqlite://",
        help="Disposable test database URL. Tests create and DROP application tables.",
    )
