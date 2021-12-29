import websockets
import asyncio
import logging
import time
import socket
import threading
import json

end_of_file_signal = '{"eof" : 1}'
max_buffer_size = 1000

class AudioWebSocket():
    """
    Pipes Audio to the Vosk server
    """
    def __init__(self, username, vosk_server, data):
        self.username = username
        self.vosk_server = vosk_server
        self.audio_queue = asyncio.Queue()
        self.log = logging.getLogger("bot")
        self.thread = threading.Thread(target=self.begin, args=([bytes(data)]))
        self.thread.start()
    
    def begin(self, data):
        asyncio.run(self.pipe(data))

    async def pipe(self, data):
        try:
            async with websockets.connect(self.vosk_server) as websocket:
                configObject = {
                    "username":self.username,
                    "config":{
                        "sample_rate":48000
                    }
                }
                await websocket.send(json.dumps(configObject))

                data_offset = 0
                while data_offset < len(data):
                    end_point = min(max_buffer_size+data_offset, len(data))
                    await websocket.send(data[data_offset:end_point])
                    data_offset = end_point
                
                await websocket.send(end_of_file_signal)
                return
        except socket.gaierror as e:
            self.log.error("received socket error: %s", e)
            time.sleep(5.0)
        except ConnectionRefusedError as e:
            self.log.error("received connection refused error: %s", e)
            time.sleep(5.0)

_sentinel = object()

class AudioWebSocketQueue:
    def __init__(self, username, vosk_server, queue):
        self.username = username
        self.vosk_server = vosk_server
        self.audio_queue = queue
        self.log = logging.getLogger("bot")
        self.thread = threading.Thread(target=self.main, args=())
        self.thread.start()
    
    def main(self):
        asyncio.run(self.pause_for_sound())

    async def pause_for_sound(self):
        buffer = []
        while True:
            try:
                while True:
                    data = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                    if data is _sentinel:
                        self.log.debug(f"completed loop for user: {self.username}")
                        return
                    buffer.extend(data)
            except asyncio.TimeoutError:
                self.log.debug(f"timeout on {self.username} queue, checking buffer length to send to websocket.")
            if len(buffer) > 0:
                    w = AudioWebSocket(self.username, self.vosk_server, buffer)
                    buffer = []



class AudioWebSocketManager:
    
    def __init__(self, vosk_server):
        self.vosk_server = vosk_server
        self.queues = {}
        self.lock = threading.Lock()

    def write(self, username, data):
        self.lock.acquire()
        if not username in self.queues:
            aq = AudioWebSocketQueue(username, self.vosk_server, asyncio.Queue())
            self.queues[username] = aq
            aq.audio_queue.put_nowait(data)
        else:
            aq = self.queues[username]
            aq.audio_queue.put_nowait(data)
        self.lock.release()

    def close(self, username):
        self.lock.acquire()
        if not username in self.queues:
            self.lock.release()
            return
        aq = self.queues[username]
        aq.audio_queue.put_nowait(_sentinel)
        del self.queues[username]
        self.lock.release()

