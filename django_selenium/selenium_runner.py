import os
import socket
import subprocess
import time
import signal
import unittest

from django.conf import settings
from django.test.simple import reorder_suite
from django.test.testcases import TestCase
from django_selenium.selenium_server import start_test_server

try:
    from django.test.simple import DjangoTestSuiteRunner
except ImportError:
    msg = """

    django-selenium requires django 1.2+.
    """
    raise ImportError(msg)

SELTEST_MODULE = 'seltests'

def wait_until_connectable(port, timeout=60):
    """Blocks until the specified port is connectable."""

    def is_connectable(port):
        """Tries to connect to the specified port."""
        try:
            socket_ = socket.socket()
            socket_.settimeout(1)
            socket_.connect(("127.0.0.1", port))
            socket_.close()
            return True
        except socket.error:
            return False

    count = 0
    while not is_connectable(port):
        if count == timeout:
            return False
        count += 1
        time.sleep(1)
    return True

class SeleniumTestRunner(DjangoTestSuiteRunner):
    """
    Test runner with Selenium support
    """

    def __init__(self, **kwargs):
        super(SeleniumTestRunner, self).__init__(**kwargs)
        self.selenium = kwargs.get('selenium')
        self.selenium_only = kwargs.get('selenium_only')

        self.test_server = None
        self.selenium_server = None

    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        suite = unittest.TestSuite()

        if not self.selenium_only:
            suite = super(SeleniumTestRunner, self).build_suite(test_labels, extra_tests, **kwargs)

        if self.selenium:
            import django.test.simple
            orig_test_module = django.test.simple.TEST_MODULE
            django.test.simple.TEST_MODULE = SELTEST_MODULE
            try:
                sel_suite = super(SeleniumTestRunner, self).build_suite(test_labels, extra_tests, **kwargs)
                suite.addTest(sel_suite)
            finally:
                 django.test.simple.TEST_MODULE = orig_test_module

        return reorder_suite(suite, (TestCase,))

    def _start_selenium(self):
        if self.selenium:
            # Set display variable
            os.environ['DISPLAY'] = settings.SELENIUM_DISPLAY
            # Start test server
            self.test_server = start_test_server(port=settings.SELENIUM_TESTSERVER_PORT)

            # Start selenium server
            assert settings.SELENIUM_PATH, "selenium path is not set"
            selenium_server_cmd = "java -jar %s" % settings.SELENIUM_PATH
            self.selenium_server = subprocess.Popen([selenium_server_cmd])

            # Waiting for server to be ready
            if not wait_until_connectable(4444):
                assert False, "selenium server does not respond"

    def _stop_selenium(self):
        if self.selenium:
            # Stop selenium server
            selenium_server = self.selenium_server
            selenium_server.send_signal(signal.SIGINT)
            if selenium_server.poll() is None:
                selenium_server.kill()
                selenium_server.wait()

            # Stop test server
            self.test_server.stop()

    def run_tests(self, test_labels, extra_tests=None, **kwargs):

        self._start_selenium()
        results = super(SeleniumTestRunner, self).run_tests(test_labels, extra_tests, **kwargs)
        self._stop_selenium()

        return results