from ... import gvars
from ..base.server import ProxyBase
from .parser import addr_reader, ss_reader


class SSProxy(ProxyBase):
    proto = "SS"

    def __init__(self, cipher, bind_addr, via=None, plugin=None, **kwargs):
        self.cipher = cipher
        self.bind_addr = bind_addr
        self.via = via
        self.plugin = plugin
        self.kwargs = kwargs
        self.ss_parser = ss_reader.parser(self.cipher)

    async def _run(self):
        if self.plugin:
            self.plugin.server = self
            self.proto += f"({self.plugin.name})"
            await self.plugin.init_server(self.client)

        addr_parser = addr_reader.parser()
        while not addr_parser.has_result:
            data = await self.recv(gvars.PACKET_SIZE)
            if not data:
                return
            addr_parser.send(data)
        self.target_addr, _ = addr_parser.get_result()
        via_client = await self.connect_server(self.target_addr)

        async with via_client:
            redundant = addr_parser.readall()
            if redundant:
                await via_client.sendall(redundant)
            await self.relay(via_client)

    async def recv(self, size):
        data = await self.client.recv(size)
        if not data:
            return data
        if hasattr(self.plugin, "decode"):
            data = self.plugin.decode(data)
            if not data:
                return await self.recv(size)
        self.ss_parser.send(data)
        return self.ss_parser.read()

    async def sendall(self, data):
        iv = b""
        if not hasattr(self, "encrypt"):
            iv, self.encrypt = self.cipher.make_encrypter()
        to_send = iv + self.encrypt(data)
        if hasattr(self.plugin, "encode"):
            to_send = self.plugin.encode(to_send)
        await self.client.sendall(to_send)
