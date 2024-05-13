"""
A wrapper around the synology API for to help with NAS access.
"""

from os import makedirs
from typing import Tuple

from annexremote import Master
from synology_api.filestation import FileStation
from tqdm import tqdm


class NAS:
    """
    A wrapper around the synology API for to help with NAS access.
    """

    def __init__(self, filestation: FileStation, annex: Master):
        if filestation is None:
            annex.debug("Filestation is None in NAS class.")

        self.filestation = filestation
        self.annex = annex

    def list_structure(self, path: str, recursive=False):
        """
        Lists the structure of the current directory.
        """

        if not self.exists(path):
            return []

        if path == "/" or path == "":
            self.annex.debug("Root.  Checking for shares.")
            result = self.filestation.get_list_share()

            self.annex.debug(f'Received "{result}" from server.')
            if "success" in result and result["success"]:
                structure = [f["path"] for f in result["data"]["shares"]]

                if recursive:
                    for directory in dirs:
                        structure.extend(
                            self.list_structure(directory, recursive=recursive)
                        )

                self.annex.debug(f'Found shares "{structure}".')
                return structure
            else:
                self.annex.debug("Could not find any shares.")
                return []

        result = self.filestation.get_file_list(path)

        if "success" in result and result["success"]:
            files_and_dirs = result["data"]["files"]
            dirs = [fd["path"] for fd in files_and_dirs if fd["isdir"]]

            structure = [f["path"] for f in files_and_dirs]

            if recursive:
                for directory in dirs:
                    structure.extend(
                        self.list_structure(directory, recursive=recursive)
                    )

            self.annex.debug(f'Found structure: "{structure}".')
            return structure
        else:
            return []

    def find_leaf_nodes(self, path: str):
        """
        Gets the leaf file system nodes from the NAS.
        """

        files_and_dirs = self.filestation.get_file_list(path)["data"]["files"]
        dirs = [fd for fd in files_and_dirs if fd["isdir"]]
        files = [fd for fd in files_and_dirs if not fd["isdir"]]

        leaf_nodes = [f["path"] for f in files]
        for directory in dirs:
            leaf_nodes.extend(self.find_leaf_nodes(directory["path"]))

        return leaf_nodes

    def download_file(self, synology_path: str, target_dir: str):
        """
        Downloads the specified file from the NAS.
        """

        self.filestation.get_file(synology_path, "download", dest_path=target_dir)

    def download_folder(self, synology_path: str, target_dir: str):
        """
        Downloads the given folder recursively.
        """

        makedirs(target_dir, exist_ok=True)

        files_and_dirs = self.filestation.get_file_list(synology_path)["data"]["files"]
        dirs = [fd for fd in files_and_dirs if fd["isdir"]]

        for directory in dirs:
            self.download_folder(directory["path"], f"{target_dir}/{directory['name']}")

        files = [fd for fd in files_and_dirs if not fd["isdir"]]

        for file in tqdm(files):
            self.download_file(file["path"], target_dir)

    def exists(self, path: str) -> bool:
        """
        Checks to see if the given directory exists.
        """
        self.annex.debug(f'Checking "{path}".')

        if path == "/" or path == "":
            return True

        try:
            parent = "/".join(path.split("/")[:-1])
            structure = self.list_structure(parent)

            if len(structure) == 0:
                self.annex.debug("Synology returned no elements.")
                return False

            return any(f for f in structure if f == path)
        except Exception as ex:
            self.annex.debug(f'Exception "{ex}" occurred.  Does not exist.')
            return False

    def create_folder(self, path: str):
        """Creates a new folder on the NAS.  Returns True for success and False for failure."""

        self.annex.debug(f'Creating folder at "{path}".')

        if self.exists(path):
            return True

        parent = "/".join(path.split("/")[:-1])
        folder = path.split("/")[-1]
        if not self.create_folder(parent):
            return False

        self.annex.debug(
            f'Performing create folder with parent: "{parent}", folder: "{folder}"'
        )
        result = self.filestation.create_folder(parent, folder)

        return "success" in result and result["success"]

    def delete_files(self, *files: Tuple[str]) -> bool:
        """Starts a delete task on the Synology NAS.  Does not wait for completion.

        Args:
            *files (str): The files to delete

        Returns:
            _type_: True for success and False for Failure
        """
        result = self.filestation.start_delete_task(files)

        return "success" in result and result["success"]

    def upload_file(self, synology_folder: str, local_file: str):
        """
        Uploads the given folder to the NAS.
        """

        self.filestation.upload_file(synology_folder, local_file)
