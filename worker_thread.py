""" This module implements async worker threads for various tasks. """
import sys
import traceback

from PyQt5.QtCore import pyqtSignal, QRunnable, QThreadPool, pyqtSlot, QObject


# Code from: https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread. A thread can only ever fail or
    succeed.
    """
    failure = pyqtSignal(tuple)
    success = pyqtSignal(object)


class WorkerThread(QRunnable):
    """
    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.
    """
    _shared_thread_pool = QThreadPool()

    def __init__(self, fn, *args, **kwargs):
        super().__init__()

        # Store constructor arguments (re-used for processing)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """
        try:
            result = self._fn(
                *self._args, **self._kwargs
            )
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print(f"Worker failed to run: {str(e)}")
            traceback.print_exc()
            exc_type, value = sys.exc_info()[:2]
            self._signals.failure.emit((exc_type, value, traceback.format_exc()))
        else:
            self._signals.success.emit(result)

    def exec(self, fn_success_callback=None, fn_error_callback=None):
        """
        Run this worker on a global thread pool. Provide callback functions.
        """
        if fn_success_callback is not None:
            self._signals.success.connect(fn_success_callback)

        if fn_error_callback is not None:
            self._signals.failure.connect(fn_error_callback)

        WorkerThread._shared_thread_pool.start(self)
