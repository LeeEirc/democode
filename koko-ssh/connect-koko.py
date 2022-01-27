
import termios
import os
from pprint import pprint
import sys
import socket
import paramiko
import yaml
import select
import fcntl
import tty
import selectors
import signal
import argparse
parser = argparse.ArgumentParser(description='ssh connect to koko')
parser.add_argument('config', type=str, default="config.yaml", help='config path')
args = parser.parse_args()
def signal_handler(signal, frame):
    print("\nprogram exiting gracefully")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def read_config(yaml_path):
    with open(yaml_path, "r", encoding="utf8") as f:
        data = f.read()
        return yaml.safe_load(data)
    return {}

def get_private_key(private_key_path,passphrase=None):
    if not private_key_path:
        return None
    return paramiko.RSAKey.from_private_key_file(private_key_path,
        password=passphrase)


if __name__ == '__main__':
    data = read_config(args.config)
    pprint(data, indent=2)
    ssh_client = paramiko.SSHClient()
    ssh_client.load_system_host_keys()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    hostname = data.get("koko_hostname", "127.0.0.1")
    port = data.get("koko_port",2222)
    username = data.get("username", "admin")
    password = data.get("password", "admin")
    private_key_path = data.get("private_key_path", None)
    private_passphrase = data.get("private_key_passphrase", None)
    private_key = get_private_key(private_key_path, private_passphrase)
    old_sz = os.get_terminal_size()
    ssh_client.connect(hostname=hostname, port=port, username=username, 
    password=password, pkey=private_key,compress=False, timeout=50, 
    disabled_algorithms=dict(pubkeys=["rsa-sha2-512", "rsa-sha2-256"]),
    allow_agent=False, look_for_keys=False)
    channel = ssh_client.invoke_shell(term='xterm-256color', width=old_sz.columns, height=old_sz.lines)
    
    def handle_resize(signum, frame):
        sz = os.get_terminal_size()
        channel.resize_pty(width=sz.columns, height=sz.lines)
    signal.signal(signal.SIGWINCH, handle_resize)
    fd = sys.stdin.fileno()
    oldtty = termios.tcgetattr(fd)
    fl = fcntl.fcntl( fd, fcntl.F_GETFL )
    fcntl.fcntl( fd, fcntl.F_SETFL, fl| os.O_NONBLOCK )
    tty.setraw(fd)
    tty.setcbreak(fd)
    # sel = selectors.DefaultSelector()
    # sel.register(fd, selectors.EVENT_READ)
    # sel.register(channel, selectors.EVENT_READ)
    # while 1:
    #     events = sel.select(timeout=60)
    #     for sock in [key.fileobj for key, _ in events]:
    #         if sock == fd:
    #             byte_data = sys.stdin.read(1024)
    #             channel.send(byte_data)
    #         if sock == channel:
    #             data = sock.recv(1024)
    #             sys.stdout.write(data.decode("utf-8"))
    while True:
        r, w, e = select.select([channel, sys.stdin], [], [])
        if channel in r:
            try:
                byte_data = channel.recv(len(channel.in_buffer))
                if len(byte_data) > 0:
                    sys.stdout.write(byte_data.decode("utf8"))
            except socket.timeout as e:
                print(e)
                break
        if sys.stdin in r:
            try:
                byte_data = sys.stdin.read(10)
                if len(byte_data)>0:
                    channel.send(byte_data)
            except Exception as e:
                print(e)
                break

    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, oldtty)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl)