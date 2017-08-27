# qwebchannel.py
python3.6 port of qwebchannel.js client library
===================================================


Requirements:
===================================================
Javascript Websocket api like websocket
In the example i have used 
https://pypi.python.org/pypi/websocket-client 

First run Qt5 standalone websocket c++ example.
http://doc.qt.io/qt-5/qtwebchannel-standalone-example.html

Then run "python3 path/of/qwebchannel.py"


Example code:
    from qwebchannel import QWebchannel
    import websocket
    import threading

    def receive_message_from_cpp(message):
        print("Received message: {}".format(message))

    def data_send_from_python(channel):
        while True:
            inp = input("Enter message: ")
            channel.objects.dialog.receiveText(inp)

    def channel_ready(channel):
        channel.objects.dialog.sendText.connect(receive_message_from_cpp)
        channel.objects.dialog.receiveText("Client connected, ready to send/receive messages!")
        thread = threading.Thread(target=data_send_from_python, args=(channel,))
        thread.setDaemon(True)
        thread.start()
        #time.sleep(1)
    def on_open(ws):
        print("Socket started")
        w = QWebchannel(ws,channel_ready)
    ws = websocket.WebSocketApp("ws://127.0.0.1:12345")
    ws.on_open = on_open
    ws.run_forever()
