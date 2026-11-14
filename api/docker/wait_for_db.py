"""Wait for PostgreSQL before running migrations or starting the server."""

import math
import os
import time

import psycopg2


def wait_for_database(database_url: str, timeout: int = 60) -> None:
    if timeout < 1:
        raise ValueError("DATABASE_WAIT_TIMEOUT must be at least 1 second")
    deadline = time.monotonic() + timeout
    while True:
        try:
            # libpq enforces a minimum of two seconds per connection attempt.
            remaining = deadline - time.monotonic()
            connection = psycopg2.connect(
                database_url, connect_timeout=max(2, min(5, math.ceil(remaining)))
            )
            connection.close()
            return
        except psycopg2.OperationalError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            print("Waiting for database...", flush=True)
            time.sleep(min(2, remaining))


if __name__ == "__main__":
    wait_for_database(
        os.environ["DATABASE_URL"], int(os.getenv("DATABASE_WAIT_TIMEOUT", "60"))
    )
