# fakentp.py - an SNTP server whose clock is this machine's plus an offset: the sandbox nodes share
# one clock, so a node's "wrong" clock is played by its reference saying another time.
#   FakeNtp(offset_s, port=0).start() -> .port; .offset may be changed; .stratum (0: unsynchronised)
import socket, struct, threading, time
NTP_EPOCH = 2208988800


class FakeNtp:
    def __init__(self, offset=0.0, port=0, host='127.0.0.1'):
        self.offset, self.stratum, self.silent = float(offset), 2, False
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind((host, port))
        self.port = self.s.getsockname()[1]
        self.asked = 0

    def _ts(self, t):
        return struct.pack('!II', int(t) + NTP_EPOCH, int((t - int(t)) * (1 << 32)))

    def _run(self):
        while True:
            try:
                data, addr = self.s.recvfrom(512)
            except OSError:
                return
            self.asked += 1
            if self.silent or len(data) < 48:
                continue
            t1 = time.time() + self.offset
            out = bytearray(48)
            out[0] = (0 << 6) | (4 << 3) | 4
            out[1] = self.stratum
            out[24:32] = data[40:48]
            out[32:40] = self._ts(t1)
            out[40:48] = self._ts(time.time() + self.offset)
            self.s.sendto(bytes(out), addr)

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def close(self):
        self.s.close()
