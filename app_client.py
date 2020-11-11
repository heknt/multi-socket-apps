#!/usr/bin/env python3

import sys
import socket
import selectors
from threading import Thread
from pynput.keyboard import Listener
import traceback
import ssl
# package with Message class
import lib_client

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    #Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

sel = selectors.DefaultSelector()

quit_key_pressed = False
stat_key_pressed = False

# Listener function
# key type - KeyCode
def on_press(key): 
    global quit_key_pressed, stat_key_pressed
    print("Press 's' for statistics or 'q' to quit.")
    try:
        if key.char is 's':
            stat_key_pressed = True
        elif key.char is 'q':
            quit_key_pressed = True
            return False
    except AttributeError as e:
        if mode == 'debug':
            print(f'error: {e}')
        elif mode == 'user':
            print('be careful with excess pressing, young man')


def detect_key_press():
    with Listener(on_press=on_press) as listener:
        print("Press 's' for statistics or 'q' to quit.")
        listener.join()


def get_traceback(message):
    print("main: error: exception for",
        f"{message.addr}:\n{traceback.format_exc()}")


def start_connection(host: str, port: int, mode: str):
    addr = (host, port)
    print("starting connection to", addr)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # sock.setblocking(False)
    sock.connect_ex(addr)

    # ctx = ssl.create_default_context()
    # ctx.verify_mode = ssl.CERT_REQUIRED
    # ctx.check_hostname = True
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations("certs/CA.pem")
    # ctx.load_cert_chain('certs/server.pem', 'certs/server.key')

    sslsoc = ctx.wrap_socket(sock, server_hostname=f'{host}:{port}')


    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = lib_client.Message(sel, sslsoc, addr, mode)
    sel.register(sslsoc, events, data=message)


if len(sys.argv) != 4:
    print("usage:", sys.argv[0], "<host> <port> <mode>")
    print("<mode> must equal to 'user' or 'debug'")
    sys.exit(1)

host, port = sys.argv[1], int(sys.argv[2])
mode = sys.argv[3]
start_connection(host, port, mode)

try:
    getch_thread = Thread(target=detect_key_press)
    getch_thread.start()
    message = None

    while not quit_key_pressed:
        events = sel.select(timeout=1)
        for key, mask in events:
            message = key.data
            try:
                if mask:
                    if stat_key_pressed:
                        message.set_request(content=b"s")
                        message.write()
                        stat_key_pressed = False
                    message.read()
            except Exception as e:
                if mode == 'debug':
                    get_traceback(message)
                elif mode == 'user':
                    print(f'error: {e}')
                message.close()
        # Check for a socket being monitored to continue
        if not sel.get_map():
            break
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    try:
        message.close()
    except Exception as e:
        if mode == 'debug':
            get_traceback(message)
        elif mode == 'user':
            print(f'error: {e}')
    sel.close()
