import constants
import websockets
import asyncio

class AudioWebSocket():
    """
    Pipes Audio to the Vosk server
    """
    def __init__(self, username, vosk_server):
        self.username = username
        self.vosk_server = vosk_server
        self.loop = asyncio.get_event_loop()
        self.audio_queue = asyncio.Queue()
        asyncio.run(self.pipe())
        
    def write(self, data):
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, bytes(data))
    
    def close(self):
        self.loop.call_soon_threadsafe(self.audio_queue.put_nowait, "END", self.username)
    
    async def pipe(self):
        async with websockets.connect(self.vosk_server) as websocket, self.audio_queue as q, self.username as username:
            await websocket.send('{ "config" : { "sample_rate" : %d } }' % (48000))
            isOpen = True
            while isOpen:
                myData = await q.get()
                if myData == "END":
                    isOpen = False
                    continue
                await websocket.send(myData)
                print(username+" says: ")
                print(await websocket.recv())
            await websocket.send('{"eof" : 1}')
            print(await websocket.recv())


class AudioWebSocketManager:
    
    def __init__(self, vosk_server):
        self.vosk_server = vosk_server
        self.websockets = {}

    def write(self, username, data):
        w = self.websockets[username]
        if not w:
            w = AudioWebSocket(username, self.vosk_server)
            self.websockets[username] = w
        w.write(data)

    def close(self, username):
        w = self.websockets[username]
        if not w:
            return
        w.close()
            
