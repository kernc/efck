import argparse
import logging
import os
import signal
import sys
import time
import tempfile
from pathlib import Path

import psutil

from . import IS_WIDOWS, __version__, CONFIG_DIRS, cli_args
from .qt import QApplication, QT_API, QT_VERSION_STR

logger = logging.getLogger(__name__)


def parse_args():
    app_name = QApplication.instance().applicationName()
    parser = argparse.ArgumentParser(
        prog=app_name,
        description='''Emoji filter / Unicode chat keyboard.
        A Qt GUI chat tool that pops up a dialog with tabs for:
        emoji filtering / selection,
        text to fancy Unicode transformation,
        GIF meme selection etc. (extensible architecture).
        Upon activation, it 'pastes' your selection into the previously active
        (focused) window, such as a web browser or a desktop chat app or similar.
        ''')
    parser.add_argument('--debug', action='store_const', dest='log_level', const=logging.DEBUG,
                        default=logging.ERROR, help='Print debug messages to stderr')
    args = parser.parse_args()
    cli_args[:] = [args]

    temp_file = Path(tempfile.gettempdir()) / f'{app_name}-{time.strftime("%Y%m%dT%H%M%S")}.log'
    logging.basicConfig(
        format='{relativeCreated:.0f}\t{levelname:8s}\t{name:15s}\t{message}',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(temp_file, encoding='utf-8', delay=True)
        ],
        force=True,
        style='{',
        level=args.log_level)
    logger.info('%s v%s', app_name, __version__)
    if args.log_level == logging.DEBUG:
        logger.info('Logging into "%s"', temp_file)


def main():
    parse_args()

    logger.info('Qt version: %s %s, platform: %s', QT_API, QT_VERSION_STR, QApplication.platformName())
    logger.info('Config directories: %s', CONFIG_DIRS)

    check_if_another_process_is_running_and_raise_it(lambda: window.show())

    from .gui import MainWindow
    from .config import load_config

    load_config()
    window = MainWindow()
    window.show()
    window.reset_hotkey_listener()
    sys.exit(QApplication.instance().exec())


def check_if_another_process_is_running_and_raise_it(signal_handler):
    OUR_SIGUSR1 = signal.SIGBREAK if IS_WIDOWS else signal.SIGUSR1

    def is_process_running(name):
        for proc in psutil.process_iter(attrs=['name', 'exe', 'cmdline', 'pid'], ad_value=None):
            if not proc:
                continue
            pinfo = proc.info
            if (((pinfo['name'] or '').startswith(name) or
                 name in (pinfo['exe'] or '') or
                 name in ' '.join(pinfo['cmdline'])) and
                    proc.pid != os.getpid()):
                logger.debug('Process match: %s %s', proc, pinfo)
                return proc

    proc = is_process_running('efck')
    if proc:
        os.kill(proc.pid, OUR_SIGUSR1)
        logger.info('efck-chat-keyboard instance is already running, '
                    'sending SIGUSR1 to pid %d. Quitting.', proc.pid)
        sys.exit(0)

    def sigusr1_handler(_signum, _frame):
        logger.info('Received SIGUSR1. Showing up!')
        nonlocal prev_handler
        signal_handler()
        if callable(prev_handler):
            prev_handler()

    prev_handler = signal.signal(OUR_SIGUSR1, sigusr1_handler)


main()
