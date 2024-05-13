"""A module which implements a git annex special remote
which allows storing files on a Synology NAS.
"""

from pathlib import Path
from typing import Callable

from annexremote import Master, RemoteError, SpecialRemote
from synology_api.filestation import FileStation

from git_annex_remote_synology.credentials import Credentials
from git_annex_remote_synology.nas import NAS


# These instance attributes are important.
class SynologyRemote(SpecialRemote):  # pylint: disable=too-many-instance-attributes
    """Implements a git annex special remote which allows storing files on a Synology NAS."""

    DEFAULT_PORT = 5000
    DEFAULT_PROTOCOL = "http"
    DEFAULT_INGORE_SSL = False
    DEFAULT_DSM_VERSION = 7

    def __init__(self, annex: Master, debug=False) -> None:
        super().__init__(annex)

        self.configs = {
            "hostname": "The hostname to your Synology NAS. (required)",
            "port": f"The port to connect to your Synology NAS.  Default: {self.DEFAULT_PORT}",
            "protocol": "The protocol to use to connect to your Synology NAS.  "
            + f"Options are 'http' or 'https'. Default: '{self.DEFAULT_PROTOCOL}'",
            "ignore_ssl": "Ignores certificate errors if connecting with https.  "
            + "Default: {self.DEFAULT_INGORE_SSL}",
            "dsm_version": "The version of DSM on your Synology NAS.  "
            + "Default: {self.DEFAULT_DSM_VERSION}",
            "path": "The path to store files.  (required)",
        }

        self.annex = annex
        self._debug = debug
        self._filestation: FileStation = None
        self._nas: NAS = None

        self._hostname: str = None
        self._port: int = None
        self._protocol: str = None
        self._ignore_ssl: bool = None
        self._dsm_version: int = None
        self._path: str = None

    def _get_or_error(self, config_name: str, type_cast: Callable = str):
        config_value = self.annex.getconfig(config_name)

        if config_value:
            return type_cast(config_value)

        raise RemoteError(f"A value for the config '{config_name}' must be provided.")

    def _get_or_default(
        self, config_name: str, default_value: any, type_cast: Callable = str
    ):
        config_value = self.annex.getconfig(config_name)

        if config_value:
            return type_cast(config_value)

        return default_value

    @property
    def hostname(self) -> str:
        """The hostname used to connect to the Synology NAS.

        Returns:
            str: The hostname used to connect to the Synology NAS.
        """
        if self._hostname is None:
            self._hostname = self._get_or_error("hostname")

        return self._hostname

    @property
    def port(self) -> int:
        """The port used to connect to the Synology NAS.

        Returns:
            int: The port used to connect to the Synology NAS.
        """
        if self._port is None:
            self._port = self._get_or_default("port", self.DEFAULT_PORT, int)

        return self._port

    @property
    def protocol(self) -> str:
        """The protocol to use when connecting to the Synology NAS.
        Can be either 'http' or 'https'.

        Raises:
            RemoteError: Raised if not 'http' or 'https'.

        Returns:
            str: The protocol to use when connecting to the Synology NAS.
        """
        if self._protocol is None:
            self._protocol = self._get_or_default("protocol", self.DEFAULT_PROTOCOL)

        if self._protocol not in {"http", "https"}:
            raise RemoteError(
                "A value for the config 'protocol' is not either 'http' or 'https'."
            )

        return self._protocol

    @property
    def ignore_ssl(self) -> bool:
        """Determines if cert errors should be ignored.

        Returns:
            bool: True if cert errors should be ignored, false otherwise.
        """
        if self._ignore_ssl is None:
            self._ignore_ssl = self._get_or_default(
                "ignore_ssl", self.DEFAULT_INGORE_SSL, bool
            )

        return self._ignore_ssl

    @property
    def dsm_version(self) -> int:
        """The version of DSM on the Synology NAS.

        Returns:
            int: The version of DSM on the Synology NAS.
        """
        if self._dsm_version is None:
            self._dsm_version = self._get_or_default(
                "dsm_version", self.DEFAULT_DSM_VERSION, int
            )

        return self._dsm_version

    @property
    def path(self) -> str:
        """The path to store the git annex files on the remote.

        Returns:
            str: The path to store the git annex files on the remote.
        """
        if self._path is None:
            self._path = self._get_or_error("path")

        return self._path

    def _authenticate(self):
        if self._filestation is None:
            try:
                self.annex.debug("Starting auth process.")
                with Credentials(
                    self.hostname, headless=True, annex=self.annex
                ) as creds:
                    if not creds.username or not creds.password:
                        self.annex.debug("Username or password was not retrieved.")
                        raise RemoteError("Username or password was not retrieved.")

                    self.annex.debug(
                        f'Found username: "{creds.username}" and password.'
                    )
                    self.annex.debug(
                        f"hostname: {self.hostname}, port: {self.port}, "
                        + f"secure: {self.protocol == 'https'}, "
                        + f"cert_verify: {not self.ignore_ssl}, dsm_version: {self.dsm_version}"
                    )

                    self._filestation = FileStation(
                        self.hostname,
                        self.port,
                        creds.username,
                        creds.password,
                        secure=self.protocol == "https",
                        cert_verify=not self.ignore_ssl,
                        dsm_version=self.dsm_version,
                        debug=self._debug,
                        otp_code=creds.totp,
                    )

                    self.annex.debug("Finished FileStation init.")
            except Exception as ex:
                self.annex.debug(f'Exception "{ex}" occurred while trying to auth.')
                raise ex

            self._nas = NAS(self._filestation, self.annex)

    def initremote(self):
        self._authenticate()

    def prepare(self):
        self._authenticate()

        if not self._nas.create_folder(self.path):
            raise RemoteError(f"Could not create path '{self.path}'.")

    def transfer_store(self, key: str, local_file: str):
        self._authenticate()

        self.annex.debug(f'Attempting to store "{local_file}" to "{key}".')

        target_parent = f"{self.path}/{key}"
        self._nas.create_folder(target_parent)
        self._nas.upload_file(target_parent, local_file)

    def transfer_retrieve(self, key: str, local_file: str):
        self._authenticate()

        self.annex.debug(f'Attempting to retrieve "{key}" and store at "{local_file}".')

        local_path = Path(local_file)
        target_parent = f"{self.path}/{key}"
        self._nas.download_file(
            f"{target_parent}/{local_path.name}", local_path.parent.as_posix()
        )

    def checkpresent(self, key):
        self._authenticate()

        return self._nas.exists(f"{self.path}/{key}")

    def remove(self, key):
        self._authenticate()

        self._nas.delete_files(f"{self.path}/{key}")
