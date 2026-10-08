"""A second copy of the program must fail loudly instead of silently sharing the first copy's port.

On Windows a listener that asks to reuse its address can bind a port that is already in use, and the oldest process keeps
getting the requests. A tester who started a new copy then kept seeing the old program, with the old code."""
import tempfile
import unittest
from pathlib import Path

from serial_story.studio.server import create_server
from serial_story.v1.provider import ScriptedProvider
from serial_story.v1.shelf import Shelf


class PortTests(unittest.TestCase):
    def test_a_second_server_cannot_take_a_port_that_is_in_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            first_shelf = Shelf(Path(tmp) / 'one', ScriptedProvider)
            first = create_server(first_shelf.root / '.legacy.db', port=0, writes=True, shelf=first_shelf)
            self.addCleanup(first.server_close)
            port = first.server_address[1]
            second_shelf = Shelf(Path(tmp) / 'two', ScriptedProvider)
            with self.assertRaises(OSError):
                second = create_server(second_shelf.root / '.legacy.db', port=port, writes=True, shelf=second_shelf)
                second.server_close()


if __name__ == '__main__':
    unittest.main()
