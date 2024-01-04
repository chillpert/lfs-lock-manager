# LFS Lock Manager

[![PyInstaller](https://github.com/chillpert/lfs-lock-manager/actions/workflows/build.yml/badge.svg)](https://github.com/chillpert/lfs-lock-manager/actions/workflows/build.yml)
[![Pylint](https://github.com/chillpert/lfs-lock-manager/actions/workflows/pylint.yml/badge.svg)](https://github.com/chillpert/lfs-lock-manager/actions/workflows/pylint.yml)

⚠️  This project is still experimental. Use it at your own risk.

This application can help you and your team to manage your LFS file locks, on both Windows and Linux. It is written in Python 3.12 with PyQt5 and
built using PyInstaller, so you do not need Python to be installed on your system.

The app was specifically made for projects based on Unreal Engine 4/5 in combination with the amazing Git LFS plugin by [ProjectBorealis](https://github.com/ProjectBorealis/UEGitPlugin) (forked from [SRomBauts](https://github.com/SRombauts/UEGitPlugin)). However, it can be used for any other LFS-initialized repository.

Pull requests are very welcome.

![Demo](https://github.com/chillpert/lfs-lock-manager/blob/main/demo.png)

## Features

- Add and remove locks
- Filter and search locks
- Easily copy and paste locks from other users
- Force unlocking for admin users
- Support for custom Git-LFS executables (e.g. [adjusted for multi-threading](https://github.com/ProjectBorealis/UEGitPlugin))
- Cross-platform (Windows and Linux)
- Dark mode 😎

## Installation

1. Make sure you have Git and Git LFS installed
2. Download the [latest release](https://github.com/chillpert/lfs-lock-manager/releases) and ship it with your project
3. Ensure that `settings.ini` is in the same directory as the executable
4. Configure `settings.ini` (at the very least, you need to modify `projectRootDirectory`)

On Windows, you currently still need GitBash for Windows which usually ships with Git.

## Build yourself

Run `pyinstaller LfsLockManager.spec` to create your executable. By default, it will be placed in `./dist`. Copy an
updated version of `settings.ini` to `./dist`.

## Credits

### Icons

- Exclamation mark By Fathema Khanom
- Reload By IYAHICON

## TODO

- [ ] Reduce overhead for (un)locking operations
- [ ] Clean up codebase (I am a beginner with Python)
- [ ] Remove Git Bash for Windows requirement
- [ ] Bug: Selection sometimes persists after certain actions
- [ ] Bug: After force unlocking another user's locks, the app switches to own locks again
- [ ] Bug: The current selection gets wiped when filtering using a string that does not match anything in the file tree
