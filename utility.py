""" This module implements application-related helper functions. """
import os
import shutil
import subprocess
import sys
from enum import Enum

from settings import Settings


class PlatformError(Exception):
    """
    A specialised error for unsupported platforms.
    """

    def __init__(self):
        self.message = "The current platform is not supported."
        super().__init__(self.message)


class GitLfsExecutableError(Exception):
    """
    A specialised error in situations where the specified Git-LFS executable is invalid.
    """

    def __init__(self):
        self.message = "Git LFS is not installed or cannot be executed."
        super().__init__(self.message)


def run_command(command: list, cwd: str, print_output=False):
    """
    This function executes the given command.
    :param command: The command as a list of strings
    :param cwd: The desired working directory
    :param print_output: Optionally prints the command's output if successful for debugging purposes
    :return: Returns the command's output if successful, otherwise an empty string
    """
    # If not root directory was specified, we will default to the Git project's root
    if cwd == "":
        cwd = get_project_root_directory()

    try:
        print("Command to run: " + str(command) + " in cwd: " + cwd)

        env = os.environ.copy()
        env['GIT_TERMINAL_PROMPT'] = '0'
        env['GIT_TRACE'] = '1'
        env['GIT_CURL_VERBOSE'] = '1'

        with subprocess.Popen(command, env=env, cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as process:
            # Wait for the process to finish and capture the output
            stdout, stderr = process.communicate()

            # Check the return code to detect errors
            return_code = process.returncode

            # Command executed successfully
            if return_code == 0:
                if print_output:
                    print("Command output:\n{%s}" % stdout.decode())

                return stdout.decode('utf-8')

            # Command execution failed
            print("Command execution failed with return code:", return_code)
            print("Error output:\n{%s}" % stderr.decode())

    # Handle any exceptions that occurred during command execution
    # pylint: disable=broad-exception-caught
    except Exception as e:
        print("An error occurred:\n{%s}" % str(e))

    return ""


def run_command_and_output_list_of_lines(command: list, cwd: str):
    """
    This function executes a command using `run_command` internally, but stores each line of the
    command's output in a list.
    :param command: The command to execute
    :param cwd: The desired working directory
    :return: The lines of the output in a list
    """
    output = run_command(command, cwd)

    # Split the output into lines and remove empty lines
    lines = output.splitlines()
    lines = [line.strip() for line in lines if line.strip()]

    # Return the list of lines
    return lines


def is_file_orphaned(relative_file_path: str):
    """
    Check if the given file is an orphaned file, i.e. a file which does not exist locally but is
    an LFS-tracked file.
    @TODO: The function's name is misleading since it only checks if the given file is actually not
    tracked by Git LFS.
    :param relative_file_path: The relative file path to a locked file
    :return: Returns true, if file is orphaned
    """
    git_lfs_tracked_files = get_git_lfs_tracked_files()
    return relative_file_path not in git_lfs_tracked_files


def get_git_lfs_tracked_files():
    """
    Retrieves all files tracked by Git LFS
    :return: Files tracked by Git LFS
    """
    if not hasattr(get_git_lfs_tracked_files, "tracked_files"):
        print("Cached LFS tracked files.")
        project_root = get_project_root_directory()
        get_git_lfs_tracked_files.tracked_files = (
            run_command_and_output_list_of_lines(
                [get_git_lfs_path(), 'ls-files', '--name-only'], project_root))

    return get_git_lfs_tracked_files.tracked_files


def is_git_installed():
    """
    This functions checks if Git is installed.
    :return: Returns true, if Git is installed
    """
    git_executable = shutil.which('git')
    if git_executable is None:
        return False

    try:
        # Run the `git --version` command
        subprocess.run([git_executable, '--version'], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def is_git_lfs_installed():
    """
    This functions checks if Git-LFS is installed and valid.
    :return: Returns true, if Git-LFS is installed
    """
    try:
        get_git_lfs_path()
    except GitLfsExecutableError as error:
        print(error.message)
        return False

    return True


def is_git_config_set():
    """
    This function validates the Git user's config.
    :return: Return true, if the Git config is set
    """
    try:
        project_root = get_project_root_directory()
        config_name = run_command(['git', 'config', 'user.name'], project_root)
        config_mail = run_command(['git', 'config', 'user.email'], project_root)
        if (config_name == '\n' or len(config_name) == 0) or (
                config_mail == '\n' or len(config_mail) == 0):
            return False
    except subprocess.CalledProcessError:
        return False

    return True


def get_git_user():
    """
    This function gets the name of the Git user on this machine.
    :return: Returns the name of the Git user
    """
    if not hasattr(get_git_user, "git_user"):
        project_root = get_project_root_directory()
        get_git_user.git_user = run_command(['git', 'config', 'user.name'],
                                            project_root).rstrip(
            "\n")

    return get_git_user.git_user


def get_git_branch():
    """
    This function retrieves the currently checked-out Git branch.
    :return: The checked-out branch
    """
    return run_command(['git', 'branch', '--show-current'], get_project_root_directory())


def is_git_user_admin():
    """
    This function checks if the Git user on this machine is listed as an admin user in the user
    settings. Admin users are all users who can use the `--force` flag on `git-lfs unlock`.
    :return: Returns true, if Git user is admin user
    """
    git_user = get_git_user()
    if git_user in Settings.git_admin_users:
        return True

    return False


def resource_path(relative_path: str):
    """
    Get absolute path to resource, works for dev and for PyInstaller
    """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def is_project_root_directory_valid():
    """
    This function validates the project root directory, i.e. the directory of the Git-LFS-enabled
    repository.
    :return:
    """
    return os.path.isdir(get_project_root_directory())


def get_git_lfs_path():
    """
    Returns the path to Git-LFS executable. This must always be executed in the project root
    directory if a custom Git-LFS executable was specified, and it is somewhere inside the project
    root.
    """
    if not hasattr(get_git_lfs_path, "git_lfs_path"):
        custom_git_lfs_path = Settings.custom_git_lfs_path
        project_root = get_project_root_directory()

        platform = get_platform()

        # Use custom LFS if provided via settings.ini
        if len(custom_git_lfs_path) > 0:
            # Verify executable for Windows
            if platform == Platform.WINDOWS:
                if os.path.isfile(project_root + custom_git_lfs_path + ".exe"):
                    get_git_lfs_path.git_lfs_path = os.path.normpath(
                        os.path.join(project_root, custom_git_lfs_path) + ".exe")
            # Verify executable for Linux
            elif platform == Platform.LINUX:
                if os.path.isfile(project_root + custom_git_lfs_path):
                    get_git_lfs_path.git_lfs_path = os.path.join(project_root,
                                                                 custom_git_lfs_path)
            else:
                raise PlatformError()
        else:
            # Verify that the default git-lfs command exists
            default_git_lfs_executable = "git-lfs"

            git_lfs_executable = shutil.which(default_git_lfs_executable)
            if git_lfs_executable is None:
                raise GitLfsExecutableError()

            try:
                subprocess.run([default_git_lfs_executable, '--version'],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, check=True)
                get_git_lfs_path.git_lfs_path = default_git_lfs_executable
            except subprocess.CalledProcessError as e:
                raise GitLfsExecutableError() from e

    return get_git_lfs_path.git_lfs_path


def get_project_root_directory():
    """
    This function retrieves the project root directory, i.e. the directory of the Git-LFS-enabled
    repository. The path must be specified in the user settings.
    :return: Returns the project root directory
    """
    full_path = os.path.join(os.getcwd(), Settings.project_root_directory)
    full_path = os.path.normpath(full_path)
    full_path = os.path.join(full_path, '')
    return full_path


class Platform(Enum):
    """ An enum for supported platforms """
    WINDOWS = 1
    LINUX = 2


def get_platform():
    """
    This function retrieves the current platform the application is run on.
    :return: Returns the current platform
    """
    if sys.platform.startswith('win'):
        return Platform.WINDOWS

    if sys.platform.startswith('linux'):
        return Platform.LINUX

    raise ValueError("Platform is not supported")
