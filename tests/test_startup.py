import errno
import unittest
from unittest.mock import Mock, patch

import server


class StartupTests(unittest.TestCase):
    def test_default_port_conflict_uses_os_assigned_port(self):
        bound = Mock()
        with patch.dict('os.environ', {}, clear=True), patch.object(
            server, 'ThreadingHTTPServer',
            side_effect=[OSError(errno.EADDRINUSE, 'Address already in use'), bound],
        ) as factory:
            self.assertIs(server.create_server(), bound)
        self.assertEqual([call.args[0] for call in factory.call_args_list],
                         [('0.0.0.0', 8765), ('0.0.0.0', 0)])

    def test_explicit_port_conflict_reports_actionable_error(self):
        with patch.dict('os.environ', {'PORT': '8765'}, clear=True), patch.object(
            server, 'ThreadingHTTPServer',
            side_effect=OSError(errno.EADDRINUSE, 'Address already in use'),
        ) as factory:
            with self.assertRaisesRegex(SystemExit, '8765.*PORT'):
                server.create_server()
        self.assertEqual(factory.call_count, 1)

    def test_other_socket_errors_are_not_treated_as_conflicts(self):
        with patch.dict('os.environ', {}, clear=True), patch.object(
            server, 'ThreadingHTTPServer', side_effect=OSError(errno.EACCES, 'Denied'),
        ) as factory:
            with self.assertRaises(OSError):
                server.create_server()
        self.assertEqual(factory.call_count, 1)
