import logging
from logdna import LogDNAHandler
import bugsnag
from bugsnag.handlers import BugsnagHandler
import sys


def get_logger():
    logger = logging.getLogger('pensieve_app')
    logger.setLevel(logging.DEBUG)
    return logger


logger = get_logger()


def configure_console_logging():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    add_handler_to_logger(console_handler)


def configure_logdna_logging(logdna_key, logdna_app):
    logdna_options = {}
    logdna_options['index_meta'] = True
    logdna_options['app'] = logdna_app
    logdna_handler = LogDNAHandler(logdna_key, logdna_options)
    logdna_handler.setLevel(logging.DEBUG)
    add_handler_to_logger(logdna_handler)


def configure_bugsnag_error_monitoring(bugsnag_key, bugsnag_release_stage):
    bugsnag.configure(
        api_key=bugsnag_key,
        project_root="./",
        notify_release_stages=["production", "staging"],
        release_stage=bugsnag_release_stage
    )
    bugsnag_handler = BugsnagHandler()
    bugsnag_handler.setLevel(logging.ERROR)
    add_handler_to_logger(bugsnag_handler)


def add_handler_to_logger(handler):
    logger.addHandler(handler)
