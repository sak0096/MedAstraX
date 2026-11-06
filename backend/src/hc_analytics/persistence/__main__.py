"""Administrative schema command.

Use a deployment-only database URL. The application runtime role should not
have DDL privileges.
"""

from __future__ import annotations

import argparse

from hc_analytics.config import get_settings
from hc_analytics.persistence.repository import SCHEMA_VERSION, StudyRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage canonical study-state schema.")
    parser.add_argument("command", choices=("migrate", "verify"))
    args = parser.parse_args()

    repository = StudyRepository.from_settings(get_settings())
    if args.command == "migrate":
        repository.migrate()
    else:
        repository.ensure_schema()
    print(f"study schema {SCHEMA_VERSION}: {args.command} complete")


if __name__ == "__main__":
    main()
