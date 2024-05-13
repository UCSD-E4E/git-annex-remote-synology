import sys
from argparse import ArgumentParser

from annexremote import Master

from git_annex_remote_synology.credentials import Credentials
from git_annex_remote_synology.synology_remote import SynologyRemote


def setup(hostname: str) -> None:
    with Credentials(hostname) as credentials:
        username = credentials.username
        password = credentials.password

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

        args = parser.parse_args()
        if args.subcommand == "setup":
            setup(args.hostname)
            return

    master = Master()
    master.LinkRemote(SynologyRemote(master))
    master.Listen()


if __name__ == "__main__":
    main()
