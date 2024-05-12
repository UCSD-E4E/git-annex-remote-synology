# git-annex special remote for Synology NAS

## Installation
```
pipx install git+https://github.com/UCSD-E4E/git-annex-remote-synology.git
```

## Upgrade
```
pipx upgrade git-annex-remote-synology
```

## Usage
1. Create a git-annex repository (walkthrough)
2. Execute `git-annex-remote-synology setup --hostname e4e-nas.ucsd.edu` to ensure that your username and password are stored.
3. Perform the `initremote`
```
git annex initremote synology type=external externaltype=synology encryption=none hostname=e4e-nas.ucsd.edu port=6021 protocol=https ignore_ssl=True dsm_version=7
```