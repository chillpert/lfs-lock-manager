""" This module defines generic user settings. """
import configparser
import dataclasses


@dataclasses.dataclass
class Settings:
    """
    This class stores user settings which are parsed from the `settings.ini` file.
    """
    # Define class-level properties
    project_root_directory = "../"
    default_expansion_depth = 3
    git_admin_users = []
    custom_git_lfs_path = ""
    default_mode = "Unlock"
    lock_mode_file_filter = ""
    tracking_branch = "main"


def load_settings():
    """
    This function parses the settings.ini config file.
    """
    # The file which we will be parsing
    file_path = "settings.ini"

    # Create a ConfigParser instance
    config = configparser.ConfigParser()

    # Read the INI file
    print(f"Reading settings.ini from '{file_path}'")
    config.read(file_path)

    # Retrieve settings from the INI file
    Settings.project_root_directory = config.get('Settings', 'projectRootDirectory')
    Settings.default_expansion_depth = config.getint('Settings', 'defaultExpansionDepth')
    users_str = config.get('Settings', 'gitAdminUsers')
    Settings.git_admin_users = [user.strip() for user in users_str.split(',')]
    Settings.custom_git_lfs_path = config.get('Settings', 'customGitLfsExecutable')
    Settings.default_mode = config.get('Settings', 'defaultMode')
    Settings.lock_mode_file_filter = config.get('Settings', 'lockModeFileFilter')
    Settings.tracking_branch = config.get('Settings', 'trackingBranch')
