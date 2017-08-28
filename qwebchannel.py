#!/usr/bin/env python3
import sys
import json
###################################################################################################
###################################################################################################
# ProjectName         : qwebchannel.py
# ProjectVersion      : 1.0.0
# ProjectDeveloper    : kawser <github.com/mkawserm> 
# ProjectDescription  : qwebchannel.js client library port for python36
###################################################################################################
###################################################################################################
class JSObject(dict):
    """Enable dictionary to access like javascript object"""
    __getattr__= dict.__getitem__
    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__
###################################################################################################
###################################################################################################
QWebChannelMessageTypes:JSObject = {
    "signal": 1,
    "propertyUpdate": 2,
    "init": 3,
    "idle": 4,
    "debug": 5,
    "invokeMethod": 6,
    "connectToSignal": 7,
    "disconnectFromSignal": 8,
    "setProperty": 9,
    "response": 10,
}
###################################################################################################
###################################################################################################
class QObject(object):
    def __getitem__(self,key):
        return self.__dict__[key]
    
    def __setitem__(self,key,value):
        self.__dict__[key] = value
    
    def __delitem__(self,key):
        del self.__dict__[key]

    def __getattr__(self,key):
        try:
            if "**dynamic_properties" in self.__dict__.keys():
                if key in self.__dict__["**dynamic_properties"].keys():
                    val = self.__dict__["**dynamic_properties"][key]._get()
                else:
                    val = super(QObject,self).__getattr__(key)
            else:
                val = self.__dict__[key]
        except Exception as e:
            #print("Ex:",e)
            val = None
        return val

    def __setattr__(self,key,value):
        if "**dynamic_properties" in self.__dict__.keys():
            if key in self.__dict__["**dynamic_properties"].keys():
                self.__dict__["**dynamic_properties"][key]._set(value)
            else:
                self.__dict__[key] = value
        else:
            self.__dict__[key] = value

    def __delattr__(self,name):
        del self.__dict__[name]

    def __init__(self,name,data,webChannel):
        super(QObject, self).__init__()
        self.__dict__ == {}
        self.__dict__["**dynamic_properties"] = {}

        self.__id__ = name
        
        webChannel.objects[name] = self

        self.__objectSignals__ = JSObject()
        
        self.__propertyCache__ = JSObject()

        _object = self

        def unwrapQObject(response):
            if isinstance(response,list):
                # support list of objects
                ret = []
                for i in response:
                    ret.append(self.unwrapQObject(i))
                return ret
            #not sure about it but without
            #it doesn't work
            if isinstance(response,str):
                return response

            if not response or "__QObject*__" not in response.keys() or "id" not in response.keys():
                return response

            objectId = response["id"]
            if webChannel.objects[objectId]:
                return webChannel.objects[objectId]

            if response["data"] is None:
                print("Cannot unwrap unknown QObject " + objectId + " without data.")
                return

            qObject = QObject( objectId, response["data"], webChannel )
            def __destroyed_func():
                if webChannel.objects[objectId] == "qObject":
                    del webChannel.objects[objectId];
                    # reset the now deleted QObject to an empty {} object
                    # just assigning {} though would not have the desired effect, but the
                    # below also ensures all external references will see the empty map
                    # NOTE: this detour is necessary to workaround QTBUG-40021
                    propertyNames = []
                    for propertyName in qObject.keys():
                        propertyNames.append(propertyName)

                    for idx in propertyNames:
                        del qObject[idx]

            qObject.destroyed.connect = __destroyed_func
            # here we are already initialized, and thus must directly unwrap the properties
            qObject.unwrapProperties()
            return qObject
        self.unwrapQObject = unwrapQObject

        def unwrapProperties():
            for propertyIdx in self.__propertyCache__.keys():
                self.__propertyCache__[propertyIdx] = self.unwrapQObject(self.__propertyCache__[propertyIdx])
        self.unwrapProperties = unwrapProperties
    
        def addSignal(signalData, isPropertyNotifySignal):
            signalName = signalData[0];
            signalIndex = signalData[1];

            _object[signalName] = JSObject()

            def __connect_func(callback):
                if not callable(callback):
                    print("Bad callback given to connect to signal " + signalName)
                    return
                if signalIndex not in _object.__objectSignals__.keys():
                    _object.__objectSignals__[signalIndex] = []
                _object.__objectSignals__[signalIndex].append(callback)
                if not isPropertyNotifySignal and signalName != "destroyed":
                        # only required for "pure" signals, handled separately for properties in propertyUpdate
                        # also note that we always get notified about the destroyed signal
                        webChannel.exec({
                            "type": QWebChannelMessageTypes["connectToSignal"],
                            "object": _object.__id__,
                            "signal": signalIndex
                        })
            def __disconnect_func(callback):
                if not callable(callback):
                    print("Bad callback given to disconnect from signal " + signalName)
                    return
                if signalIndex not in _object.__objectSignals__.keys():
                    _object.__objectSignals__[signalIndex] = []
                
                try:
                    idx = _object.__objectSignals__[signalIndex].index(callback)
                except:
                    idx = -1
                
                if idx == -1:
                    print("Cannot find connection of signal " + signalName + " to " + callback)
                    return
                _object.__objectSignals__[signalIndex].remove(idx)
                if not isPropertyNotifySignal and len(_object.__objectSignals__[signalIndex]) == 0:
                    # only required for "pure" signals, handled separately for properties in propertyUpdate
                    webChannel.exec({
                        "type": QWebChannelMessageTypes["disconnectFromSignal"],
                        "object": _object.__id__,
                        "signal": signalIndex
                        })
            _object[signalName].connect = __connect_func
            _object[signalName].disconnect = __disconnect_func

        def invokeSignalCallbacks(signalName, signalArgs):
            connections = self.__objectSignals__[signalName];
            if connections:
                for callback in connections:
                    callback(signalArgs)

        def propertyUpdate(signals, propertyMap):
            # update property cache
            for propertyIndex in propertyMap.keys():
                propertyValue = propertyMap[propertyIndex]
                self.__propertyCache__[propertyIndex] = propertyValue

            for signalName in signals.keys():
                # Invoke all callbacks, as signalEmitted() does not. This ensures the
                # property cache is updated before the callbacks are invoked.
                invokeSignalCallbacks(signalName, signals[signalName])
        self.propertyUpdate = propertyUpdate


        def signalEmitted(signalName, signalArgs):
            invokeSignalCallbacks(signalName, signalArgs)
        self.signalEmitted = signalEmitted

        def addMethod(methodData):
            methodName = methodData[0];
            methodIdx = methodData[1];

            def func(*arguments):
                args = []
                callback = None
                for i in arguments:
                    if callable(i):
                        callback = i
                    else:
                        args.append(i)

                def func2(response):
                    if response is not None:
                        result = self.unwrapQObject(response);
                        if callback:
                            callback(result)
                webChannel.exec({
                    "type": QWebChannelMessageTypes["invokeMethod"],
                    "object": self.__id__,
                    "method": methodIdx,
                    "args": args
                },func2)
            _object[methodName] = func

        def bindGetterSetter(propertyInfo):
            propertyIndex = propertyInfo[0]
            propertyName = propertyInfo[1]
            notifySignalData = propertyInfo[2]
            # initialize property cache with current value
            # NOTE: if this is an object, it is not directly unwrapped as it might
            # reference other QObject that we do not know yet
            self.__propertyCache__[propertyIndex] = propertyInfo[3]

            if notifySignalData:
                if notifySignalData[0] == 1:
                    #signal name is optimized away, reconstruct the actual name
                    notifySignalData[0] = propertyName + "Changed"
                addSignal(notifySignalData, True)
            
            def __get_f():
                propertyValue = _object.__propertyCache__[propertyIndex]
                if propertyValue == None:
                    # This shouldn't happen
                    print("Undefined value in property cache for property \"" + propertyName + "\" in object " + _object.__id__)
                return propertyValue

            def __set_f(value):
                if value == None:
                    print("Property setter for " + propertyName + " called with undefined value!")
                    return
                _object.__propertyCache__[propertyIndex] = value;
                webChannel.exec({
                    "type": QWebChannelMessageTypes["setProperty"],
                    "object": _object.__id__,
                    "property": propertyIndex,
                    "value": value
                });
            self.__dict__["**dynamic_properties"][propertyName] = JSObject()
            self.__dict__["**dynamic_properties"][propertyName]._set = __set_f
            self.__dict__["**dynamic_properties"][propertyName]._get = __get_f
        for method in data["methods"]:
            addMethod(method)
        for prop in data["properties"]:
            bindGetterSetter(prop)
        for signal in data["signals"]:
            addSignal(signal, False)
###################################################################################################
###################################################################################################
class QWebchannel(object):
    """QWebchannel port for python3.6"""
    def __init__(self, transport, initCallback):
        super(QWebchannel, self).__init__()
        if not isinstance(transport,object) or not callable(transport.send):
            raise Exception("The QWebChannel expects a transport object with a send function and onmessage callback property." + " Given is: transport: " + str(type(transport)) + ", transport.send: " + str(type(transport.send)))

        self.initCallback = initCallback
        self.channel = self
        self.transport = transport
        #print(transport.on_message)
        def onmessage(transport,message):
            global QWebChannelMessageTypes
            data = message
            if type(data) == str:
                data = json.loads(data)
            #print(type(data))
            if data["type"] == QWebChannelMessageTypes["signal"]:
                self.channel.handleSignal(data)
            elif data["type"] == QWebChannelMessageTypes["response"]:
                self.channel.handleResponse(data)
            elif data["type"] == QWebChannelMessageTypes["propertyUpdate"]:
                self.channel.handlePropertyUpdate(data)
            else:
                print("invalid message received:",message)
        self.transport.on_message = onmessage

        self.execCallbacks = {}
        self.execId = 0
        #self.exec = method defined
        self.objects = JSObject()
        #self.handleSignal = method defined

        def _init_callback(data):
            global QWebChannelMessageTypes
            for objectName in data.keys():
                _object = QObject(objectName, data[objectName], self.channel)
            # now unwrap properties, which might reference other registered objects
            for objectName in self.channel.objects.keys():
                self.channel.objects[objectName].unwrapProperties()
            if self.initCallback:
                self.initCallback(self.channel)
            self.channel.exec({"type": QWebChannelMessageTypes["idle"]})
        self.channel.exec({"type": QWebChannelMessageTypes["init"]},_init_callback)

    def handleSignal(self,message):
        _object = self.channel.objects[message["object"]]
        if _object:
            _object.signalEmitted(message["signal"], message["args"]);
        else:
            print("Unhandled signal: " + message["object"] + "::" + message["signal"])
    
    def handleResponse(self,message):
        if not "id" in message.keys():
            print("Invalid response message received: ", json.loads(message))
            return
        self.channel.execCallbacks[message["id"]](message["data"])
        del self.channel.execCallbacks[message["id"]]

    def handlePropertyUpdate(self,message):
        global QWebChannelMessageTypes
        for i in message["data"].keys():
            data = message["data"][i];
            _object = self.channel.objects[data["object"]]
            if _object:
                _object.propertyUpdate(data["signals"], data["properties"])
            else:
                print("Unhandled property update: " + data["object"] + "::" + data["signal"])
        self.channel.exec({"type": QWebChannelMessageTypes["idle"]})

    def debug(self,message):
        self.channel.send({"type":QWebChannelMessageTypes["debug"],"data":message})

    def exec(self,data,callback=None):
        if callback==None:
            self.channel.send(data)
            return
        if self.channel.execId == sys.maxsize:
            self.channel.execId = 0
        if "id" in data.keys():
            print("Cannot exec message with property id: " + json.dumps(data))
            return

        self.channel.execId = self.channel.execId+1
        data["id"] = self.channel.execId
        self.channel.execCallbacks[self.channel.execId] = callback
        self.channel.send(data)

    def send(self,data):
        if type(data) != str:
            data = json.dumps(data)
        self.transport.send(data)
###################################################################################################
###################################################################################################
if __name__ == "__main__":
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
    def on_open(ws):
        print("Socket started")
        w = QWebchannel(ws,channel_ready)
    ws = websocket.WebSocketApp("ws://127.0.0.1:12345")
    ws.on_open = on_open
    ws.run_forever()
###################################################################################################
###################################################################################################