"""A module containing an object representing credentials used for access a Synology NAS.
Returns username, password, and TOTP.
"""

import shlex
from getpass import getpass
from os import getenv, makedirs
from pathlib import Path
from sqlite3 import Connection, Cursor, OperationalError, connect
from subprocess import PIPE, CompletedProcess, run

import backoff
import keyring
from annexremote import Master, RemoteError
from appdirs import user_config_dir

SERVICE_ID_SUFFIX = "git-annex-remote-synology"
USERNAME_ENV_NAME = "NAS_USERNAME"
PASSWORD_ENV_NAME = "NAS_PASSWORD"
TOTP_COMMAND_ENV_NAME = "NAS_TOTP_COMMAND"


# These instance attributes are important.
class Credentials:  # pylint: disable=too-many-instance-attributes
    """An object representing credentials used for access a Synology NAS.
    Returns username, password, and TOTP.
    """

    def __init__(self, hostname: str, headless=False, annex: Master = None) -> None:
        self._hostname = hostname
        self._headless = headless
        self._annex = annex

        self._username: str = None
        self._totp_command: str = None

        self._connection: Connection = None
        self._cursor: Cursor = None

    @property
    def hostname(self) -> str:
        """The hostname associated with this credential.

        Returns:
            str: The hostname associated with this credential.
        """
        return self._hostname

    @property
    def username(self) -> str:
        """The password associated with this credential.

        Raises:
            RemoteError: Raised if the username returned is None.

        Returns:
            str: The password associated with this credential.
        """
        username = self._get_username()

        if not username:
            username = self._prompt_username()
            self.username = username

        if username:
            self._debug(f'Successfully returned username "{username}".')
        else:
            self._debug("Username was not returned successfully.")
            raise RemoteError("Username cannot be null.")

        return username

    @username.setter
    def username(self, username: str):
        self._save_username(username, self.totp_command)

        self._username = username

    @property
    def password(self) -> str:
        """The password associated with this credential.  This is always collected from the password
        store.

        Raises:
            RemoteError: Raised if the password returned by the password store is None.

        Returns:
            str: password associated with this credential.
        """
        self._debug("Starting get password.")
        password = self._get_password()
        self._debug("Finished get password.")

        if not password:
            self._debug("Starting password prompt.")
            password = self._prompt_password()
            self.password = password

        if password:
            self._debug("Successfully returned password.")
        else:
            self._debug("Password was not returned successfully.")
            raise RemoteError("Password cannot be null.")

        return password

    @password.setter
    def password(self, password: str):
        self._save_password(password)

    @property
    def service_id(self) -> str:
        """The service ID that uniquely identifies this credential.

        Returns:
            str: The service ID that uniquely identifies this credential.
        """
        return f"{self.hostname}-{SERVICE_ID_SUFFIX}"

    @property
    def totp_command(self) -> str:
        """The command for getting the TOTP needed to login.

        Returns:
            str: The command to get the TOTP needed to login.
        """
        totp_command = self._get_totp_command()
        self._debug(f'TOTP Command in Property: "{totp_command}".')

        return totp_command

    @totp_command.setter
    def totp_command(self, totp_command: str):
        self._save_username(self.username, totp_command)

        self._totp_command = totp_command

    @property
    def totp(self) -> str:
        """Executes the command specified in self.totp_command and returns the result.

        Returns:
            str: The result from running the command stored in self.totp_command.
        """
        totp = None
        if self.totp_command:
            totp_result: CompletedProcess = run(
                shlex.split(self.totp_command), stdout=PIPE, check=True
            )
            totp = totp_result.stdout.decode("utf8")

        self._debug(f"TOTP: {totp}")

        return totp

    def __enter__(self):
        config_path = self._get_config_path()
        db_path = config_path / "config.db"

        self._connection = connect(db_path)
        self._cursor = self._connection.cursor()

        self._create_users_table()

        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self._cursor.close()
        self._connection.close()

        return True

    def _debug(self, statement: str):
        if self._annex:
            self._annex.debug(statement)

    @backoff.on_exception(backoff.expo, OperationalError)
    def _create_users_table(self):
        self._cursor.execute(
            """CREATE TABLE IF NOT EXISTS Users
               (hostname TEXT NOT NULL UNIQUE, username TEXT NOT NULL, totp_command TEXT)
            """
        )
        self._connection.commit()

    def _get_password(self) -> str:
        password = getenv(PASSWORD_ENV_NAME)

        if password:
            self.password = password
        else:
            password = keyring.get_password(self.service_id, self.username)

        return password

    def _get_username(self) -> str:
        username = getenv(USERNAME_ENV_NAME)

        if username:
            self.username = username
        elif self._username:
            return self._username
        else:
            result = self._cursor.execute(
                "SELECT username FROM users WHERE hostname = ?", (self.hostname,)
            ).fetchone()
            username = result[0] if result else None

        return username

    def _get_totp_command(self) -> str:
        totp_command = getenv(TOTP_COMMAND_ENV_NAME)
        self._debug(f"TOTP Command: {totp_command}")

        if totp_command:
            self.totp_command = totp_command
        else:
            result = self._cursor.execute(
                "SELECT totp_command FROM users WHERE hostname = ?",
                (self.hostname,),
            ).fetchone()
            totp_command = result[0] if result else None

        return totp_command

    def _get_config_path(self) -> Path:
        config_dir = Path(
            user_config_dir(SERVICE_ID_SUFFIX, "Engineers for Exploration")
        )
        makedirs(config_dir.absolute().as_posix(), exist_ok=True)

        return config_dir

    def _prompt_password(self) -> str:
        if self._headless:
            raise RemoteError("Password has not been stored.  Please rerun setup.")

        return getpass()

    def _prompt_username(self) -> str:
        if self._headless:
            raise RemoteError("User name has not been stored.  Please rerun setup.")

        return input("User Name: ")

    def _save_password(self, password: str):
        keyring.set_password(self.service_id, self.username, password)

    def _save_username(self, username: str, totp_command: str):
        self._cursor.execute(
            """INSERT INTO Users (hostname, username, totp_command)
               VALUES (?, ?, ?)
               ON CONFLICT (hostname) DO
               UPDATE SET username=excluded.username, totp_command=excluded.totp_command;""",
            (self.hostname, username, totp_command or ""),
        )

        self._connection.commit()

    def delete_password(self):
        """Deletes the password associated with this credential from the password store."""
        keyring.delete_password(self.service_id, self.username)
