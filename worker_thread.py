import sys
import traceback

from PyQt5.QtCore import pyqtSignal, QRunnable, QThreadPool, pyqtSlot, QObject


# Code from: https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/

class WorkerSignals(QObject):
    failure = pyqtSignal(tuple)
    success = pyqtSignal(object)


class WorkerThread(QRunnable):
    _shared_thread_pool = QThreadPool()

    def __init__(self, fn, *args, **kwargs):
        super(WorkerThread, self).__init__()

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
        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self._fn(
                *self._args, **self._kwargs
            )
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            # print("Emitting failure.")
            self._signals.failure.emit((exctype, value, traceback.format_exc()))
        else:
            # print("Emitting success.")
            self._signals.success.emit(result)  # Return the result of the processing

    def exec(self, fn_success_callback=None, fn_error_callback=None):
        """
        Run this worker on a global thread pool. Provide callback functions.
        """
        if fn_success_callback is not None:
            self._signals.success.connect(fn_success_callback)

        if fn_error_callback is not None:
            self._signals.failure.connect(fn_error_callback)

        WorkerThread._shared_thread_pool.start(self)
