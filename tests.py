import unittest
import socket
import threading
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from server import Server
from database import Base, User, Room, Message, PrivateMessage, db, user_room_table

def wait_for_condition(check_function, timeout=5, interval=0.1):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_function():
            return True
        time.sleep(interval)
    return False


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        cls.session = cls.Session()
        cls.server = Server(session=cls.session)

        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        wait_for_condition(lambda: cls.server.server.fileno() != -1)

    def setUp(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(('127.0.0.1', 12345))
        self.client.recv(1024)

    def tearDown(self):
        self.client.close()

    def send_command(self, command):
        self.client.sendall(command.encode() + b'\n')
        response = self.client.recv(1024).decode().strip()
        return response

    def test_username(self):
        response = self.send_command("/username test")
        self.assertEqual(response, "/username ok")
        self.send_command("/exit")

if __name__ == "__main__":
    unittest.main()
