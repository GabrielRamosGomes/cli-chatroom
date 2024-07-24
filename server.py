import socket
import threading
from collections import defaultdict, deque
from database import db, User, Room, Message, PrivateMessage

class Server:

    def __init__(self, host='127.0.0.1', port=12345):
        self.allowed_loggout_commands = ['/exit', '/register', '/login']
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
            '/register': self.handle_register,
            '/login': self.handle_login,
        }

    def start(self):
        print("Server started...")
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()

    def handle_client(self, conn):
        conn.sendall(b"/login <username> <password> | /register <username> <password> \n")
        username = None
        while True:
            try:
                msg = conn.recv(1024).decode().strip()
                if not msg:
                    continue

                command, *args = msg.split(' ', 1)
                args = args[0] if args else ""
                
                username = self.get_username_from_conn(conn) or username
                if not username and command not in self.allowed_loggout_commands:
                    response = "/login required"
                elif command in self.commands:
                    response = self.commands[command](args, username, conn)
                else:
                    response = "/unknown command"

                if command == '/username' and response == '/username ok':
                    with self.lock:
                        username = args
                        self.clients[username] = conn
                        self.rooms['#welcome'].append(username)

                if command == '/exit':
                    if username:
                        with self.lock:
                            current_room = self.get_user_room(username)
                            if current_room:
                                self.rooms[current_room].remove(username)
                            del self.clients[username]
                    conn.sendall(response.encode() + b'\n')
                    conn.close()
                    break

                conn.sendall(response.encode() + b'\n')
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"Error: {e}")
                break
        conn.close()

    def handle_login(self, args, username, conn):
        if not args:
            return "/login <username> <password>"
        
        username, password = args.split(' ', 1)
        user = db.get_session().query(User).filter_by(username=username).first()
        if not user or not user.check_password(password):
            return "/login failed"
        
        self.clients[username] = conn
        self.rooms['#welcome'].append(username)
        return "/login ok"

    def handle_register(self, args, username, conn):
        if not args:
            return "/register <username> <password>"
        
        username, password = args.split(' ', 1)

        if db.get_session().query(User).filter_by(username=username).first():
            return "/register username_taken"

        user = User(username=username)
        user.set_password(password)
        with db.get_session() as session:
            session.add(user)
            session.commit()

        return "/register ok now login with /login <username> <password>"

    def handle_username(self, args, username, conn):
        if not args:
            return "/username required"
        if args in self.clients:
            return "/username taken"
        return "/username ok"

    def handle_exit(self, args, username, conn):
        return "/exit ok"

    def handle_room(self, args, username, conn):
        room = self.get_user_room(username)
        return f"/room {room}" if room else "/room none"

    def handle_rooms(self, args, username, conn):
        return f"/rooms {', '.join(self.rooms.keys())}"

    def handle_create(self, args, username, conn):
        if not args:
            return "/create room_required"
        if args in self.rooms:
            return "/create room_exists"
        with self.lock:
            self.rooms[args] = []
        return "/create ok"

    def handle_join(self, args, username, conn):
        if not args or args not in self.rooms:
            return "/join no_room"
        with self.lock:
            current_room = self.get_user_room(username)
            if current_room:
                self.rooms[current_room].remove(username)
            self.rooms[args].append(username)
        return "/join ok"

    def handle_users(self, args, username, conn):
        room = self.get_user_room(username)
        return f"/users {', '.join(self.rooms.get(room, []))}" if room else "/users none"

    def handle_allusers(self, args, username, conn):
        with self.lock:
            all_users = [f"{user}@{room}" for room, users in self.rooms.items() for user in users]
        return f"/allusers {', '.join(all_users)}"

    def handle_msg(self, args, username, conn):
        room = self.get_user_room(username)
        if room:
            message = f"({username} @{room}) {args}"
            with self.lock:
                self.messages[room].append(message)
                for user in self.rooms[room]:
                    if user != username:
                        self.clients[user].sendall((message + '\n').encode())
            return "/msg sent"
        return "/msg failed"

    def handle_msgs(self, args, username, conn):
        room = self.get_user_room(username)
        if room:
            with self.lock:
                if not self.messages[room]:
                    return "/msgs none"
                messages = "\n".join(self.messages[room])
                self.messages[room].clear()
            return f"/msgs\n{messages}"
        return "/msgs none"

    def handle_pmsg(self, args, username, conn):
        if len(args.split(' ', 1)) < 2:
            return "/pmsg usage"
        recipient, private_msg = args.split(' ', 1)
        if recipient not in self.clients:
            return "/pmsg no_user"
        message = f"({username} @private) {private_msg}"
        with self.lock:
            self.private_messages[recipient].append(message)
        self.clients[recipient].sendall((message + '\n').encode())
        return "/pmsg sent"

    def handle_pmsgs(self, args, username, conn):
        with self.lock:
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

    def get_username_from_conn(self, conn):
        with self.lock:
            for username, connection in self.clients.items():
                if connection == conn:
                    return username
        return None

if __name__ == "__main__":
    server = Server()
    server.start()