import configparser


class Settings:
    # Define class-level properties
    project_root_directory = "../"
    default_expansion_depth = 3
    git_admin_users = []
    custom_git_lfs_path = "git lfs"
    default_mode = "Unlocking Mode"
    lock_mode_file_filter = r"Content/"

    @classmethod
    def load_from_file(cls, file_path):
        # Create a ConfigParser instance
        config = configparser.ConfigParser()

        # Read the INI file
        print("Reading settings.ini from '%s'" % file_path)
        config.read(file_path)

        # Retrieve settings from the INI file
        cls.project_root_directory = config.get('Settings', 'projectRootDirectory')
        cls.default_expansion_depth = config.getint('Settings', 'defaultExpansionDepth')
        users_str = config.get('Settings', 'gitAdminUsers')
        cls.git_admin_users = [user.strip() for user in users_str.split(',')]
        cls.custom_git_lfs_path = config.get('Settings', 'customGitLfsExecutable')
        cls.default_mode = config.get('Settings', 'defaultMode')
        cls.lock_mode_file_filter = config.get('Settings', 'lockModeFileFilter')
