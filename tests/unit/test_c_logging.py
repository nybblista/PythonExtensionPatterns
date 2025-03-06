import logging
import sys

import pytest

from cPyExtPatt.Logging import cLogging

#: Default log format (terse)
DEFAULT_OPT_LOG_FORMAT = '%(asctime)s %(process)d %(levelname)-8s %(message)s'
#: Default log format (verbose)
DEFAULT_OPT_LOG_FORMAT_VERBOSE = '%(asctime)s - %(filename)-16s#%(lineno)-4d - %(process)5d - (%(threadName)-10s) - %(levelname)-8s - %(message)s'

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format=DEFAULT_OPT_LOG_FORMAT)

logger = logging.getLogger(__file__)


def _test_logging():
    logger.setLevel(logging.DEBUG)
    logger.warning('Test warning message XXXX')
    logger.debug('Test debug message XXXX')
    assert 0


def test_c_logging_dir():
    result = dir(cLogging)
    assert result == [
        'CRITICAL',
        'DEBUG',
        'ERROR',
        'EXCEPTION',
        'INFO',
        'WARNING',
        '__doc__',
        '__file__',
        '__loader__',
        '__name__',
        '__package__',
        '__spec__',
        'c_file_line_function',
        'log',
        'py_file_line_function',
        'py_log_set_level',
    ]


def _test_c_logging_log():
    print()
    cLogging.py_log_set_level(10)
    result = cLogging.log(cLogging.ERROR, "Test log message")
    assert result is not None


def _test_c_file_line_function_file():
    file, line, function = cLogging.c_file_line_function()
    assert file == 'src/cpy/Logging/cLogging.c'
    assert line == 148
    assert function == 'c_file_line_function'


def _test_py_file_line_function_file():
    file, _line, _function = cLogging.py_file_line_function()
    assert file == __file__


def _test_py_file_line_function_line():
    _file, line, _function = cLogging.py_file_line_function()
    assert line == 50


def _test_py_file_line_function_function():
    _file, _line, function = cLogging.py_file_line_function()
    assert function == 'test_py_file_line_function_function'
