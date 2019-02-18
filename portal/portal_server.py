from threading import Thread
import socket

class PortalServer(Thread):
    def __init__(self, address):
        super().__init__(name='portal_thread')
        self.sock = None
        self.connection = None
        self.is_listening = False
        self.is_closing = False
        self.is_running = True
        self.is_receiving = False
        self.is_sending = False
        self.received_data = None
        self.sending_data = None
        self.address = address
        self.accept_timeout = 5
        print('PortalServer: Initialized.')

    def run(self):
        while self.is_running:
            if self.is_listening:
                if self.sock is None:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.bind(self.address)
                    self.sock.listen(1)
                    self.sock.settimeout(self.accept_timeout)
                    print('PortalServer: Waiting for connection.')
                    try:
                        connection, client_address = self.sock.accept()
                        self.connection = connection
                        print('PortalServer: Connection from {0}.'.format(client_address))
                    except socket.timeout as e:
                        print('PortalServer: Connection timeout.')
                self.is_listening = False

            if self.is_closing:
                if self.sock is not None:
                    if self.connection is not None:
                        self.connection.close()
                        self.connection = None
                        print('PortalServer: Connection closed.')
                    self.sock.close()
                    self.sock = None
                self.is_closing = False

            if self.is_receiving:
                if self.connection is not None and self.sock is not None:
                    self.received_data = self.connection.recv(1024).decode()
                    print('PortalServer: Data received.')
                self.is_receiving = False

            if self.is_sending:
                if self.connection is not None and self.sock is not None:
                    self.connection.send(self.sending_data.encode())
                    print('PortalServer: Data sended.')
                self.is_sending = False

    def close_connection(self):
        self.is_closing = True

    def stop(self):
        self.is_running = False

    def listen_connection(self):
        self.is_listening = True

    def receive_message(self):
        self.is_receiving = True

    def send_message(self, message):
        self.is_sending = True
        self.sending_data = message

    def get_splitted_data(self):
        if self.received_data is None:
            return None
        result = []
        for d in self.received_data.split('|'):
            result.append(d.split(':'))
        return result