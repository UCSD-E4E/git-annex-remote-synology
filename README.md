# git-annex special remote for Synology NAS
This provides a [special remote](https://git-annex.branchable.com/special_remotes/web/) for `git annex` for storage on a Synology NAS.

## Installation
```
pipx install git+https://github.com/UCSD-E4E/git-annex-remote-synology.git
```

## Upgrade
```
pipx uninstall git-annex-remote-synology
pipx install git+https://github.com/UCSD-E4E/git-annex-remote-synology.git
```
Using the `pipx upgrade` command is not currently supported since the repo does not have a version increment yet.

## Initialize 
1. In an existing git repo, run `git annex init`.
2. Execute `git-annex-remote-synology setup --hostname e4e-nas.ucsd.edu` to ensure that your username and password are stored.
3. Perform the `initremote`
```
git annex initremote synology type=external externaltype=synology encryption=none hostname=e4e-nas.ucsd.edu port=6021 protocol=https ignore_ssl=True dsm_version=7 path=/fishsense/git-annex/pyFishSenseDev
```

## Setup on clone
1. Enable the remote 
```
git annex enableremote synology
```
2. Download the data
```
git annex copy --from=synology 
```