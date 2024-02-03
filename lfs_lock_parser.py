import os

from PyQt5.QtCore import QThread, QThreadPool

import worker_thread
from utility import Utility
from worker_thread import WorkerThread


class LfsLockData:
    def __init__(self, lock_id, lock_owner, relative_path, is_orphaned, is_local_file=True):
        self.lock_id = lock_id
        self.lock_owner = lock_owner
        self.relative_path = relative_path
        self.is_orphaned = is_orphaned  # True, if file exists locally and was never pushed to a remote branch
        self.is_local_file = is_local_file  # True, if file exists locally


class LfsLockParser:
    lock_data = []
    lock_owners = []
    subscribers = []

    has_parsed_once = False

    @staticmethod
    def get_lock_owner_of_file(relative_file_path: str):
        lock_data = LfsLockParser.get_lock_data_of_file(relative_file_path)
        if lock_data is not None:
            return lock_data.lock_owner

        return

    @staticmethod
    def get_lock_data_of_file(relative_file_path: str):
        unquoted_file_path = relative_file_path.replace('"', '')

        for lock_data in LfsLockParser.lock_data:
            if isinstance(lock_data, LfsLockData):
                if lock_data.relative_path == unquoted_file_path:
                    return lock_data

        return

    @staticmethod
    def subscribe_to_update(subscriber):
        # print("New lock data update subscriber")
        LfsLockParser.subscribers.append(subscriber)

    @staticmethod
    def _on_parsing_failed(error):
        print("LFS lock parser failed")
        print(error)

    @staticmethod
    def _notify_subscribers():
        print("Notifying subscribers %i" % len(LfsLockParser.subscribers))
        # Only notify if we actually parsed any data successfully
        if LfsLockParser.has_parsed_once:
            print("Notifying %i subscribers." % len(LfsLockParser.subscribers))
            for subscriber in LfsLockParser.subscribers:
                subscriber.on_lock_data_update()

    @staticmethod
    def parse_locks_async():
        worker = WorkerThread(LfsLockParser._parse_locks)
        worker.exec(LfsLockParser._notify_subscribers, LfsLockParser._on_parsing_failed)

    @staticmethod
    def _on_finished_parsing():
        print("Finished parsing (slot 2)")

    @staticmethod
    def _parse_locks():
        if not Utility.is_git_installed() or not Utility.is_git_lfs_installed():
            print("Failed to parse LFS data. Dependencies are missing.")
            return

        print("Parsing locks")

        # Get the lines of the output as a list
        project_root = Utility.get_project_root_directory()

        git_lfs_path = Utility.get_git_lfs_path()

        # Use backwards slash on Windows, so we can run in cmd
        if Utility.get_platform() == Utility.Platform.Windows:
            git_lfs_path = git_lfs_path.replace("/", "\\")

        command = git_lfs_path + " locks"
        lines = Utility.run_command_and_output_list_of_lines(command, project_root)

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
            is_orphaned = Utility.is_file_orphaned(file_path) and is_local_file
            # if is_orphaned:
            #     print("File '%s' is orphaned." % file_path)

            data.append(LfsLockData(lock_id, lock_owner, file_path, is_orphaned, is_local_file))

        # Keep a copy of the parsed data
        LfsLockParser.lock_data = data

        # Cache unique lock owners
        LfsLockParser.lock_owners = Utility.get_lock_owners(data)

        LfsLockParser.has_parsed_once = True

        print("Finished parsing locks")
