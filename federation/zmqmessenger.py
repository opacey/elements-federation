#!/usr/bin/env python3
import zmq
import json
import logging
import socket
from .messenger import Messenger

TOPIC_NEW_BLOCK = '10'
TOPIC_NEW_SIG   = '20'

zmq_context = zmq.Context()
zmq_poller = zmq.Poller()

def mogrify(topic, msg):
    return topic + ' ' + json.dumps(msg)

def demogrify(topicmsg):
    json0 = topicmsg.find('{')
    topic = topicmsg[0:json0].strip()
    msg = json.loads(topicmsg[json0:])
    return topic, msg

class ZmqProducer:
    def __init__(self, host, port):
        self.socket = zmq_context.socket(zmq.PUB)
        self.socket.bind("tcp://%s:%d" % ('*', port))
        zmq_poller.register(self.socket, zmq.POLLOUT)

    def __del__(self):
        zmq_poller.unregister(self.socket)
        self.socket.close()

    def send_message(self, msg, topic):
        self.socket.send(mogrify(topic, msg).encode("ascii", "strict"))

class ZmqConsumer:
    def __init__(self, host, port, proxy=None):
        self.socket = zmq_context.socket(zmq.SUB)
        if proxy != None:
            self.socket.setsockopt(zmq.SOCKS_PROXY, proxy)
        self.socket.setsockopt(zmq.RECONNECT_IVL, 500)
        self.socket.setsockopt(zmq.RECONNECT_IVL_MAX, 10000)
        self.host = host
        self.port = port
        self.socket.connect("tcp://%s:%d" % (host, port))
        self.socket.setsockopt(zmq.SUBSCRIBE, "{}".format(TOPIC_NEW_BLOCK).encode("ascii", "strict"))
        self.socket.setsockopt(zmq.SUBSCRIBE, "{}".format(TOPIC_NEW_SIG).encode("ascii", "strict"))
        zmq_poller.register(self.socket, zmq.POLLIN)

    def __del__(self):
        zmq_poller.unregister(self.socket)
        self.socket.close()

    def read_message(self):
        if self.socket not in dict(zmq_poller.poll()):
            return None, None
        return demogrify(self.socket.recv().decode())

class ZmqMessenger(Messenger):
    def __init__(self, nodes, my_id):
        Messenger.__init__(self, nodes, my_id)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.consumers = []
        self.nodes = nodes
        self.my_id = my_id
        for i, node in enumerate(nodes):
            host, port = node.split(':', 1)
            if i == my_id:
                self.producer = ZmqProducer(host, int(port))
            else:
                self.consumers.append(ZmqConsumer(host, int(port)))

    def produce(self, topic, message):
        self.producer.send_message(message, topic)

    def produce_block(self, block, height):
        message = {'height': height, 'block': block}
        self.produce(TOPIC_NEW_BLOCK, message)

    def produce_sig(self, sig, height):
        message = {'height': height, 'sig': sig}
        self.produce(TOPIC_NEW_SIG, message)

    def consume(self, topics):
        messages = []
        for consumer in self.consumers:
            while True:
                msg_topic, msg = consumer.read_message()
                if msg != None and msg_topic in topics:
                    messages.append(msg)
                else:
                    break
        return messages

    def consume_block(self, height):
        consumer = self.consume([TOPIC_NEW_BLOCK])
        for message in consumer:
            if message.get('height', 0) == height + 1:
                return message.get('block', "")
        return None

    def consume_sigs(self, height):
        sigs = []
        consumer = self.consume([TOPIC_NEW_SIG])
        for message in consumer:
            if message.get('height', 0) == height + 1:
                sigs.append(message.get('sig', ""))
        return sigs

    def reconnect(self):
        self.logger.info("Reconnecting consumers...")
        self.consumers = []
        for i, node in enumerate(self.nodes):
            host, port = node.split(':', 1)
            if i != self.my_id:
                self.consumers.append(ZmqConsumer(host, int(port)))

                # Test the given consumer node for a response and log the result
                s = socket.socket()
                try:
                    s.connect((host, int(port)))
                except Exception as e:
                    self.logger.info("    Re-registering node %s at %s:%d = Failed: %s", i, host, int(port), e)
                else:
                    self.logger.info("    Re-registering node %s at %s:%d = Succeeded", i, host, int(port))
                finally:
                    s.close()

            else:
                self.logger.info("    Skipping self: node %s at %s:%d", i, host, int(port))
