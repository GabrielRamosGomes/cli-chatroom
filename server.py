import socket
import threading
from collections import defaultdict, deque

class Server:
    def __init__(self, host='127.0.0.1', port=12345):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(5)
        self.rooms = {'#welcome': []}
        self.clients = {}
        self.lock = threading.Lock()
        self.messages = defaultdict(deque)
        self.private_messages = defaultdict(deque)
        self.commands = {
            '/username': self.handle_username,
            '/exit': self.handle_exit,
            '/room': self.handle_room,
            '/rooms': self.handle_rooms,
            '/create': self.handle_create,
            '/join': self.handle_join,
            '/users': self.handle_users,
            '/allusers': self.handle_allusers,
            '/msg': self.handle_msg,
            '/msgs': self.handle_msgs,
            '/pmsg': self.handle_pmsg,
            '/pmsgs': self.handle_pmsgs,
            '/help': self.handle_help,
        }

    def start(self):
        print("Server started...")
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.handle_client, args=(conn,)).start()

    def handle_client(self, conn):
        conn.sendall(b"/username required\n")
        username = None
        while True:
            try:
                msg = conn.recv(1024).decode().strip()
                if not msg:
                    continue

                command, *args = msg.split()
                if command in self.commands:
                    response = self.commands[command](args, username, conn)
                else:
                    response = "/unknown command"

                if command == '/username' and response == '/username ok':
                    username = args[0]
                    self.clients[username] = conn
                    self.rooms['#welcome'].append(username)

                if command == '/exit':
                    if username:
                        self.rooms[self.get_user_room(username)].remove(username)
                        del self.clients[username]
                    conn.sendall(response.encode() + b'\n')
                    conn.close()
                    break

                conn.sendall(response.encode() + b'\n')
            except ConnectionResetError:
                break

    def handle_username(self, args, username, conn):
        if not args:
            return "/username required"
        if args[0] in self.clients:
            return "/username taken"
        return "/username ok"

    def handle_exit(self, args, username, conn):
        return "/exit ok"

    def handle_room(self, args, username, conn):
        return f"/room {self.get_user_room(username)}"

    def handle_rooms(self, args, username, conn):
        return f"/rooms {', '.join(self.rooms.keys())}"

    def handle_create(self, args, username, conn):
        if not args:
            return "/create room_required"
        if args[0] in self.rooms:
            return "/create room_exists"
        self.rooms[args[0]] = []
        return "/create ok"

    def handle_join(self, args, username, conn):
        if not args or args[0] not in self.rooms:
            return "/join no_room"
        current_room = self.get_user_room(username)
        self.rooms[current_room].remove(username)
        self.rooms[args[0]].append(username)
        return "/join ok"

    def handle_users(self, args, username, conn):
        return f"/users {', '.join(self.rooms[self.get_user_room(username)])}"

    def handle_allusers(self, args, username, conn):
        all_users = [f"{user}@{room}" for room, users in self.rooms.items() for user in users]
        return f"/allusers {', '.join(all_users)}"

    def handle_msg(self, args, username, conn):
        current_room = self.get_user_room(username)
        message = f"({username} @{current_room}) {' '.join(args)}"
        self.messages[current_room].append(message)
        for user in self.rooms[current_room]:
            if user != username:
                self.clients[user].sendall((message + '\n').encode())
        return "/msg sent"

    def handle_msgs(self, args, username, conn):
        current_room = self.get_user_room(username)
        if not self.messages[current_room]:
            return "/msgs none"
        messages = "\n".join(self.messages[current_room])
        self.messages[current_room].clear()
        return f"/msgs\n{messages}"

    def handle_pmsg(self, args, username, conn):
        if len(args) < 2 or args[0] not in self.clients:
            return "/pmsg no_user"
        recipient, private_msg = args[0], ' '.join(args[1:])
        message = f"({username} @private) {private_msg}"
        self.private_messages[recipient].append(message)
        self.clients[recipient].sendall((message + '\n').encode())
        return "/pmsg sent"

    def handle_pmsgs(self, args, username, conn):
        if not self.private_messages[username]:
            return "/pmsgs none"
        messages = "\n".join(self.private_messages[username])
        self.private_messages[username].clear()
        return f"/pmsgs\n{messages}"

    def handle_help(self, args, username, conn):
        return ("/help: Show this help message\n"
                "/username <name>: Assigns a username\n"
                "/exit: Ends the session\n"
                "/room: Shows current room\n"
                "/rooms: Lists all available rooms\n"
                "/create <room>: Creates a new room\n"
                "/join <room>: Joins an existing room\n"
                "/users: Lists users in the current room\n"
                "/allusers: Lists all users and their respective rooms\n"
                "/msg <message>: Sends a message to the current room\n"
                "/msgs: Retrieves messages from the queue\n"
                "/pmsg <username> <message>: Sends a private message\n"
                "/pmsgs: Retrieves private messages from the queue\n")

    def get_user_room(self, username):
        for room, users in self.rooms.items():
            if username in users:
                return room
        return None

if __name__ == "__main__":
    server = Server()
    server.start()
