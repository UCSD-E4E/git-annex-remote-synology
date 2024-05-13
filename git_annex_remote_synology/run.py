import sys
from argparse import ArgumentParser

from annexremote import Master
from synology_api.filestation import FileStation

from git_annex_remote_synology.credentials import Credentials
from git_annex_remote_synology.synology_remote import SynologyRemote


def setup(hostname: str, clear_password) -> None:
    with Credentials(hostname) as creds:
        if clear_password:
            creds.delete_password()

        username = creds.username
        password = creds.password

        if username and password:
            print(f"We found a password for {username}.")
        else:
            print("We failed to collect username and password.")


def main() -> None:
    """Entry point for the Synology NAS git annex extension."""
    if len(sys.argv) > 1:
        parser = ArgumentParser()
        subparsers = parser.add_subparsers(dest="subcommand")

        parser_setup = subparsers.add_parser(
            "setup",
            help="Authenticate with Synology to prepare for initremote/enableremote",
        )
        parser_setup.add_argument(
            "--hostname",
            type=str,
            help="The hostname of your Synology NAS.",
            required=True,
        )
        parser_setup.add_argument(
            "--clear-password",
            action="store_true",
            help="Clears the password from the password store.",
        )

        args = parser.parse_args()
        if args.subcommand == "setup":
            setup(args.hostname, args.clear_password)
            return

    master = Master()
    master.LinkRemote(SynologyRemote(master))
    master.Listen()


if __name__ == "__main__":
    main()
