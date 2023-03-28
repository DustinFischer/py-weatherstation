from abc import ABC, abstractmethod
from enum import Enum
from pprint import pprint

from confluent_kafka import Consumer as ConfluentKafkaConsumer
from confluent_kafka.serialization import SerializationContext, StringDeserializer, MessageField

from eventbus import get_bootstrap_servers
from eventbus.events import EventRegistry
from eventbus.events.deserialize import EventDeserializer


class ConsumerError(Exception):
    pass


class OffsetResetType(Enum):
    LATEST = 'latest'
    EARLIEST = 'earliest'


class AbstractConsumer(ABC):
    GROUP_ID = None  # group id for managing offsets
    TOPICS = []  # TODO: define some structure
    OFFSET_RESET: OffsetResetType = OffsetResetType.LATEST  # offset when no offset for group is present
    AUTO_COMMIT = True  # auto commit periodically, async (True), manual (False)
    POLL_WAIT = 1.0  # how long to wait between successive polls (how long poll will block while awaiting new data)

    _consumer_memo = None
    _consumer_cls = ConfluentKafkaConsumer

    def __init__(self, bootstrap_servers=None, name=None, group_id=None, session_timeout=45,
                 auto_create_topic=True):
        # TODO: metrics client...
        self._bootstrap_servers = bootstrap_servers
        self._auto_commit = self.AUTO_COMMIT
        self._offset_reset = self.OFFSET_RESET
        self._name = name or self.__class__.__name__
        self._group_id = group_id or self.GROUP_ID
        self._session_timeout = session_timeout
        self._auto_create_topic = auto_create_topic
        # ...
        self._topic_vals = [t for t in self.TOPICS]

    @property
    def _consumer(self):
        if self._consumer_memo is None:
            # instantiate consumer instance
            config = self._get_consumer_config()
            self._consumer_memo = self._consumer_cls(config)
        return self._consumer_memo

    def _get_consumer_config(self) -> dict:
        # https://docs.confluent.io/platform/current/installation/configuration/consumer-configs.html
        # https://docs.confluent.io/5.5.1/clients/librdkafka/md_CONFIGURATION.html
        # https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html#kafka-client-configuration
        config = {
            'bootstrap.servers': self._bootstrap_servers or get_bootstrap_servers(),
            'group.id': self._group_id,
            'enable.auto.commit': self._auto_commit,
            'auto.offset.reset': self._offset_reset,
            'client.id': self._name,
            'session.timeout.ms': int(self._session_timeout) * 1000,
            'allow.auto.create.topics': self._auto_create_topic,
            'error_cb': self._on_global_error
        }
        return config

    def _on_global_error(self, err):
        # TODO: investigate, flesh out
        print(f'{self._name} - global error - {err}')

    def subscribe(self, on_assign=None):
        # subscribe to topics
        self._consumer.subscribe(self._topic_vals, on_assign=on_assign)

    def _on_assign(self, consumer, partitions):
        print(f'Assigned ({consumer}): {partitions}')

    def start(self, on_assign=True):
        on_assign_cb = self._on_assign if on_assign is True else None

        # subscribe to topics
        self.subscribe(on_assign=on_assign_cb)

        # enter polling loop (thread this out if needs be)
        try:
            while True:
                # https://docs.confluent.io/platform/current/clients/confluent-kafka-python/html/index.html#message
                msg = self._consumer.poll(self.POLL_WAIT)
                # continue polling if no data received
                if msg is None:
                    continue
                # log error and resume polling
                if msg.error():
                    # TODO: log
                    print(msg.error())
                    continue
                    # raise ConsumerError(f'Consumer data error (name: {self._name}) - {data.error()}')

                # TODO: support different serialization schemes (avro, json)
                # deserialize key to human-readable
                key_ctx = SerializationContext(msg.topic(), MessageField.KEY)
                key_de = StringDeserializer()
                de_key = key_de(msg.key(), key_ctx)
                msg.set_key(de_key)

                # deserialize value to human-readable
                # event = EventRegistry.get()  # TODO: implement to get correct subclass type
                headers = {name: val.decode() for name, val in msg.headers()}
                event_cls = EventRegistry.get(headers.get('name'))
                event = event_cls(msg.value(), headers=headers)

                # deserialize the event payload
                de = EventDeserializer(event)
                msg.set_value(de.deserialize())

                # process the event data
                print(f'[{self._name}] received new event')
                pprint({
                    'headers': msg.headers(),
                    'topic': msg.topic(),
                    'partition': msg.partition(),
                    'key': msg.key(),
                    'timestamp': msg.timestamp(),
                    'value': msg.value()
                })
                self.process_event(msg.value(), log=msg)
        finally:
            # TODO: log
            print(f'[{self._name}] closing consumer')
            self._consumer.close()

    @abstractmethod
    def process_event(self, event, log=None):
        # event: parsed / constructed event
        # log: original payload from poll()
        raise NotImplementedError('All consumer processes must define this method')
