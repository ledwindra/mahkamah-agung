import os
from random import randint

class Proxy:

    def __init__(self):
        self.proxy_user = os.environ["PROXY_USER"]
        self.proxy_password = os.environ["PROXY_PASSWORD"]
        self.proxy_port = os.environ["PROXY_PORT"]

    def get_host(self):
        file_name = "host.txt"
        if os.path.exists(file_name):
            host = open(file_name, "r").read().split("\n")
            index = randint(0, len(host)-1)

            return host[index]

    def get_proxy(self):
        proxy = f"socks5h://{self.proxy_user}:{self.proxy_password}@{self.get_host()}:{self.proxy_port}"

        return proxy
