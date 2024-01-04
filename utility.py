import os
import shutil
import subprocess
import sys
from enum import Enum

from settings import Settings


class PlatformError(Exception):
    def __init__(self):
        self.message = "The current platform is not supported."
        super().__init__(self.message)


class GitLfsExecutableError(Exception):
    def __init__(self):
        self.message = "Git LFS is not installed or cannot be executed."
        super().__init__(self.message)


class Utility:
    @staticmethod
    def run_command(command, directory):
        root_directory = Utility.get_project_root_directory()
        root = root_directory if directory == "" else directory

        try:
            # Execute the command in a subprocess
            split_command = command.split()
            process = subprocess.Popen(split_command, cwd=root, stdout=subprocess.PIPE)

            # Wait for the process to finish and capture the output
            stdout, stderr = process.communicate()

            # Check the return code to detect errors
            return_code = process.returncode
            if return_code == 0:
                # Command executed successfully
                # print("Command output:")
                # print(stdout.decode())
                return stdout.decode('utf-8')
            else:
                # Command execution failed
                print("Command execution failed with return code:", return_code)
                print("Error output:")
                print(stderr.decode())
        except Exception as e:
            # Handle any exceptions that occurred during command execution
            print("An error occurred:", str(e))

        return ""

    @staticmethod
    def run_command_and_output_list_of_lines(command, directory):
        output = Utility.run_command(command, directory)

        # Split the output into lines and remove empty lines
        lines = output.splitlines()
        lines = [line.strip() for line in lines if line.strip()]

        # Return the list of lines
        return lines

    @staticmethod
    def get_locked_files():
        return Utility.run_command_and_output_list_of_lines('git lfs locks')

    @staticmethod
    def is_file_orphaned(relative_file_path):
        git_lfs_tracked_files = Utility.get_git_lfs_tracked_files()
        return relative_file_path not in git_lfs_tracked_files

    @staticmethod
    def get_git_lfs_tracked_files():
        if not hasattr(Utility.get_git_lfs_tracked_files, "tracked_files"):
            print("Cached LFS tracked files.")
            project_root = Utility.get_project_root_directory()
            Utility.get_git_lfs_tracked_files.tracked_files = Utility.run_command_and_output_list_of_lines(
                "git-lfs ls-files --name-only", project_root)

        return Utility.get_git_lfs_tracked_files.tracked_files

    @staticmethod
    def is_git_installed():
        git_executable = shutil.which('git')
        if git_executable is None:
            return False

        try:
            # Run the `git --version` command
            subprocess.run([git_executable, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def is_git_lfs_installed():
        try:
            Utility.get_git_lfs_path()
            return True
        except GitLfsExecutableError as error:
            print(error.message)
            return False

    @staticmethod
    def is_git_config_set():
        try:
            project_root = Utility.get_project_root_directory()
            config_name = Utility.run_command("git config user.name", project_root)
            config_mail = Utility.run_command("git config user.email", project_root)
            if (config_name != '\n' and not len(config_name) == 0) and (
                    config_mail != '\n' and not len(config_mail) == 0):
                return True
            else:
                return False
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def get_git_user():
        if not hasattr(Utility.get_git_user, "git_user"):
            project_root = Utility.get_project_root_directory()
            Utility.get_git_user.git_user = Utility.run_command('git config user.name', project_root).rstrip("\n")

        return Utility.get_git_user.git_user

    @staticmethod
    def is_git_user_admin():
        git_user = Utility.get_git_user()
        if git_user in Settings.git_admin_users:
            return True

        return False

    @staticmethod
    def resource_path(relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)

    @staticmethod
    def is_project_root_directory_valid():
        return os.path.isdir(Utility.get_project_root_directory())

    @staticmethod
    def get_git_lfs_path():
        """
        Returns the path to git-lfs executable. This must always be executed in the project root directory.
        """
        if not hasattr(Utility.get_git_lfs_path, "git_lfs_path"):
            custom_git_lfs_path = Settings.custom_git_lfs_path
            project_root = Utility.get_project_root_directory()

            platform = Utility.get_platform()

            # Use custom LFS if provided via settings.ini
            if len(custom_git_lfs_path) > 0:
                # Verify executable for Windows
                if platform == Utility.Platform.Windows:
                    if os.path.isfile(project_root + custom_git_lfs_path + ".exe"):
                        Utility.get_git_lfs_path.git_lfs_path = custom_git_lfs_path
                # Verify executable for Linux
                elif platform == Utility.Platform.Linux:
                    if os.path.isfile(project_root + custom_git_lfs_path):
                        Utility.get_git_lfs_path.git_lfs_path = custom_git_lfs_path
                else:
                    raise PlatformError()
            else:
                # Verify that the default git-lfs command exists
                default_git_lfs_executable = "git-lfs"

                git_lfs_executable = shutil.which(default_git_lfs_executable)
                if git_lfs_executable is None:
                    raise GitLfsExecutableError()

                try:
                    subprocess.run([default_git_lfs_executable, '--version'], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, check=True)
                    Utility.get_git_lfs_path.git_lfs_path = default_git_lfs_executable
                except subprocess.CalledProcessError:
                    raise GitLfsExecutableError()

        return Utility.get_git_lfs_path.git_lfs_path

    @staticmethod
    def get_project_root_directory():
        # full_path = Utility.resource_path(os.getcwd().replace("\\", "/") + "/" + Settings.project_root_directory +
        # "/")
        full_path = os.path.join(os.getcwd(), Settings.project_root_directory)
        return os.path.join(full_path, '')

    class Platform(Enum):
        Windows = 1
        Linux = 2

    @staticmethod
    def get_platform():
        if sys.platform.startswith('win'):
            return Utility.Platform.Windows
        elif sys.platform.startswith('linux'):
            return Utility.Platform.Linux

        ValueError("Platform is not supported")

    @staticmethod
    def get_lock_owners(lock_data):
        owners = set()

        for data in lock_data:
            owners.add(data.lock_owner)

        return list(owners)
