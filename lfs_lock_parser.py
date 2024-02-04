""" This module implements a parser for Git LFS lock data and related types. """
import os
import dataclasses

import utility
from worker_thread import WorkerThread


@dataclasses.dataclass
class LfsLockData:
    """
    This type implements all data which can be retrieved from Git LFS file locks.
    """
    lock_id: int
    lock_owner: str
    relative_path: str
    # True, if file exists locally and was never pushed to a remote branch
    is_orphaned: bool
    # True, if file exists locally
    is_local_file: bool


class LfsLockParser:
    """
    This class provides functions to asynchronously parse LFS lock data generated by 'git-lfs
    locks'.
    """
    lock_data = []
    lock_owners = []
    subscribers = []

    has_parsed_once = False

    @staticmethod
    def get_lock_owner_of_file(relative_file_path: str):
        """
        This helper function retrieves the owner of a given file.
        :param relative_file_path: The relative file path of a locked file
        :return: The owner of the file
        """
        lock_data = LfsLockParser.get_lock_data_of_file(relative_file_path)
        if lock_data is not None:
            return lock_data.lock_owner

        return ""

    @staticmethod
    def get_lock_data_of_file(relative_file_path: str):
        """
        This helper function retrieves the stored lock data of a given file.
        :param relative_file_path: The relative file path of a locked file
        :return: The lock data of the file
        """
        unquoted_file_path = relative_file_path.replace('"', '')

        for lock_data in LfsLockParser.lock_data:
            if isinstance(lock_data, LfsLockData):
                if lock_data.relative_path == unquoted_file_path:
                    return lock_data

        return ""

    @staticmethod
    def get_lock_owners(lock_data: [LfsLockData]):
        """
        This function retrieves all unique LFS lock owners, i.e. all users who own file locks.
        :param lock_data: The LFS lock data to use
        :return: Returns all unique LFS lock owners
        """
        owners = set()

        for data in lock_data:
            owners.add(data.lock_owner)

        return list(owners)

    @staticmethod
    def subscribe_to_update(subscriber):
        """
        This function is used to have an object subscribe to parsing updates of this class.
        :param subscriber: The object that wants to be notified
        """
        LfsLockParser.subscribers.append(subscriber)

    @staticmethod
    def _on_parsing_failed(error):
        print("LFS lock parser failed: " + error)

    @staticmethod
    def _notify_subscribers():
        # Only notify if we actually parsed any data successfully
        if LfsLockParser.has_parsed_once:
            print(f"Notifying {len(LfsLockParser.subscribers)} subscribers.")
            for subscriber in LfsLockParser.subscribers:
                subscriber.on_lock_data_update()
        else:
            print("Failed to notify %i subscribers because there is no valid data.")

    @staticmethod
    def parse_locks_async():
        """
        Asynchronously parses LFS lock data. Once finished, all subscribers will be notified.
        """
        worker = WorkerThread(LfsLockParser._parse_locks)
        worker.exec(LfsLockParser._notify_subscribers, LfsLockParser._on_parsing_failed)

    @staticmethod
    def _parse_locks():
        if not utility.is_git_installed() or not utility.is_git_lfs_installed():
            print("Failed to parse LFS data. Dependencies are missing.")
            return

        print("Parsing locks")

        # Get the lines of the output as a list
        project_root = utility.get_project_root_directory()

        command = [utility.get_git_lfs_path(), 'locks']
        lines = utility.run_command_and_output_list_of_lines(command, project_root)

        data = []

        for line in lines:
            # Split the data string into components
            components = line.split()

            # Extract the relevant information
            file_path = components[0]
            lock_owner = components[1]
            lock_id = components[2].split(":")[1]  # Extract the number part after "ID:"

            # Does the file exists locally?
            is_local_file = os.path.isfile(project_root + file_path)

            # Is the file an orphaned file, meaning it does not exist anywhere on the remote?
            is_orphaned = utility.is_file_orphaned(file_path) and is_local_file
            # if is_orphaned:
            #     print("File '%s' is orphaned." % file_path)

            data.append(LfsLockData(lock_id, lock_owner, file_path, is_orphaned, is_local_file))

        # Keep a copy of the parsed data
        LfsLockParser.lock_data = data

        # Cache unique lock owners
        LfsLockParser.lock_owners = LfsLockParser.get_lock_owners(data)

        LfsLockParser.has_parsed_once = True

        print("Finished parsing locks")
