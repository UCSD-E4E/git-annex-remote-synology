from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from annexremote import Master, RemoteError, SpecialRemote
from synology_api.filestation import FileStation

from git_annex_remote_synology.credentials import Credentials
from git_annex_remote_synology.nas import NAS


class SynologyRemote(SpecialRemote):
    def __init__(self, annex: Master, debug=False) -> None:
        super().__init__(annex)

        self.DEFAULT_PORT = 5000
        self.DEFAULT_PROTOCOL = "http"
        self.DEFAULT_INGORE_SSL = False
        self.DEFAULT_DSM_VERSION = 7

        self.configs = {
            "hostname": "The hostname to your Synology NAS. (required)",
            "port": f"The port to connect to your Synology NAS.  Default: {self.DEFAULT_PORT}",
            "protocol": "The protocol to use to connect to your Synology NAS.  "
            + f"Options are 'http' or 'https'. Default: '{self.DEFAULT_PROTOCOL}'",
            "ignore_ssl": f"Ignores certificate errors if connecting with https.  "
            + "Default: {self.DEFAULT_INGORE_SSL}",
            "dsm_version": f"The version of DSM on your Synology NAS.  "
            + "Default: {self.DEFAULT_DSM_VERSION}",
            "path": "The path to store files.  (required)",
        }

        self.annex = annex
        self._debug = debug
        self._filestation: FileStation = None
        self._nas: NAS = None

    def _get_or_error(self, config_name: str, type_cast: Callable = str):
        config_value = self.annex.getconfig(config_name)

        if config_value:
            return type_cast(config_value)
        else:
            raise RemoteError(
                f"A value for the config '{config_name}' must be provided."
            )

    def _get_or_default(
        self, config_name: str, default_value: any, type_cast: Callable = str
    ):
        config_value = self.annex.getconfig(config_name)

        if config_value:
            return type_cast(config_value)
        else:
            return default_value

    @property
    def hostname(self) -> str:
        if not hasattr(self, "_hostname"):
            self._hostname = self._get_or_error("hostname")

        return self._hostname

    @property
    def port(self) -> int:
        if not hasattr(self, "_port"):
            self._port = self._get_or_default("port", self.DEFAULT_PORT)

        return self._port

    @property
    def protocol(self) -> str:
        if not hasattr(self, "_protocol"):
            self._protocol = self._get_or_default("protocol", self.DEFAULT_PROTOCOL)

        if self._protocol not in {"http", "https"}:
            raise RemoteError(
                f"A value for the config 'protocol' is not either 'http' or 'https'."
            )

        return self._protocol

    @property
    def ignore_ssl(self) -> bool:
        if not hasattr(self, "_ignore_ssl"):
            self._ignore_ssl = self._get_or_default(
                "ignore_ssl", self.DEFAULT_INGORE_SSL, bool
            )

        return self._ignore_ssl

    @property
    def dsm_version(self) -> int:
        if not hasattr(self, "_dsm_version"):
            self._dsm_version = self._get_or_default(
                "dsm_version", self.DEFAULT_DSM_VERSION, int
            )

        return self._dsm_version

    @property
    def path(self) -> str:
        if not hasattr(self, "_path"):
            self._path = self._get_or_error("path")

        return self._path

    def _authenticate(self):
        if self._filestation is None:
            try:
                self.annex.debug("Starting auth process.")
                with Credentials(
                    self.hostname, headless=True, annex=self.annex
                ) as creds:
                    filestation = FileStation(
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

                    self._filestation = filestation
            except Exception as ex:
                self.annex.debug(f'Exception "{ex}" occurred while trying to auth.')
                raise RemoteError(
                    f"Authentication to {self.hostname}:{self.port} failed."
                )

            self._nas = NAS(self._filestation, self.annex)

    def initremote(self):
        self._authenticate()

    def prepare(self):
        self._authenticate()

        if not self._nas.create_folder(self.path):
            raise RemoteError(f"Could not create path '{self.path}'.")

    def transfer_store(self, key, local_file):
        self._authenticate()

        local_path = Path(local_file)
        with TemporaryDirectory() as target_dir:
            local_target = Path(target_dir) / key

            local_path.symlink_to(local_target)
            self._nas.upload_file(self.path, local_target)

    def transfer_retrieve(self, key: str, local_file: str):
        self._authenticate()

        local_path = Path(local_file)
        with TemporaryDirectory() as target_dir:
            local_target = Path(target_dir) / key

            self._nas.download_file(f"{self.path}/{key}", target_dir)
            local_target.rename(local_path)

    def checkpresent(self, key):
        self._authenticate()

        return self._nas.exists(f"{self.path}/{key}")

    def remove(self, key):
        self._authenticate()

        self._nas.delete_files(f"{self.path}/{key}")
