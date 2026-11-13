"""Local PostgreSQL 16 for development and tests, without Docker.

Uses the PostgreSQL binaries bundled in the ``pgserver`` Python package
(installed with requirements-dev.txt), so nothing system-wide is installed and
no administrator rights are needed.

    python -m scripts.dev_db start    Create (first run) and start the server
    python -m scripts.dev_db stop     Stop the server
    python -m scripts.dev_db status   Show whether it is running
    python -m scripts.dev_db url      Print the DATABASE_URL to use

Data lives outside the repository (and outside OneDrive) in
%LOCALAPPDATA%\\EranovaOrbit\\pgdata on Windows, ~/.local/share/eranova-orbit
elsewhere. The server only listens on 127.0.0.1 and trusts local connections;
it is for development only and must never be exposed.
"""

import os
import subprocess
import sys
from pathlib import Path

PORT = int(os.environ.get("ORBIT_PGPORT", "5433"))
USER = "orbit"
DATABASES = ("orbit_dev", "orbit_test")


def data_root() -> Path:
    override = os.environ.get("ORBIT_PGDATA")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EranovaOrbit"
    return Path.home() / ".local" / "share" / "eranova-orbit"


DATA_DIR = data_root() / "pgdata"
LOG_FILE = data_root() / "postgres.log"


def binary(name: str) -> str:
    try:
        import pgserver
    except ImportError:
        sys.exit("pgserver is not installed. Run: pip install -r requirements-dev.txt")
    suffix = ".exe" if sys.platform == "win32" else ""
    path = Path(pgserver.__file__).parent / "pginstall" / "bin" / f"{name}{suffix}"
    if not path.exists():
        sys.exit(f"PostgreSQL binary not found: {path}")
    return str(path)


def database_url(database: str = "orbit_dev") -> str:
    return f"postgresql+asyncpg://{USER}@127.0.0.1:{PORT}/{database}"


def is_running() -> bool:
    if not (DATA_DIR / "PG_VERSION").exists():
        return False
    result = subprocess.run(
        [binary("pg_ctl"), "status", "-D", str(DATA_DIR)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def initialise() -> None:
    DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"Creating database cluster in {DATA_DIR} ...")
    subprocess.run(
        [
            binary("initdb"),
            "-D",
            str(DATA_DIR),
            "-U",
            USER,
            "--auth=trust",
            "-E",
            "UTF8",
            "--locale=C",
        ],
        stdout=subprocess.DEVNULL,
        check=True,
    )


def ensure_databases() -> None:
    psql = binary("psql")
    for name in DATABASES:
        exists = subprocess.run(
            # -w: never prompt for a password; fail instead of hanging.
            [
                psql,
                "-w",
                "-h",
                "127.0.0.1",
                "-p",
                str(PORT),
                "-U",
                USER,
                "-d",
                "postgres",
                "-tAc",
                f"SELECT 1 FROM pg_database WHERE datname = '{name}'",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if exists != "1":
            subprocess.run(
                [binary("createdb"), "-w", "-h", "127.0.0.1", "-p", str(PORT), "-U", USER, name],
                stdin=subprocess.DEVNULL,
                check=True,
            )
            print(f"Created database {name}")


def start() -> None:
    if not (DATA_DIR / "PG_VERSION").exists():
        initialise()
    if is_running():
        print("PostgreSQL is already running.")
    else:
        stale_pid = DATA_DIR / "postmaster.pid"
        if stale_pid.exists():
            stale_pid.unlink()
        # Output goes to the log file; inheriting this process's pipes would keep
        # callers waiting for as long as the server runs.
        subprocess.run(
            [
                binary("pg_ctl"),
                "start",
                "-D",
                str(DATA_DIR),
                "-l",
                str(LOG_FILE),
                "-w",
                "-o",
                f"-p {PORT} -h 127.0.0.1",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        print(f"PostgreSQL started on 127.0.0.1:{PORT}")
    ensure_databases()
    print(f"DATABASE_URL={database_url()}")
    print(f"TEST_DATABASE_URL={database_url('orbit_test')}")


def stop() -> None:
    if not is_running():
        print("PostgreSQL is not running.")
        return
    subprocess.run([binary("pg_ctl"), "stop", "-D", str(DATA_DIR), "-m", "fast"], check=True)


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "start":
        start()
    elif command == "stop":
        stop()
    elif command == "status":
        print("running" if is_running() else "stopped", f"(data: {DATA_DIR}, port {PORT})")
    elif command == "url":
        print(database_url())
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
