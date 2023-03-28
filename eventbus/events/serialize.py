from abc import ABC
from abc import abstractmethod
from typing import Callable, Type

from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import SerializationContext
from confluent_kafka.serialization import Serializer, MessageField

from eventbus import get_config
from eventbus.events import (
    AbstractEvent,
    AbstractEventWithSchema,
    AbstractAvroEventWithSchema,
    AbstractJsonEventWithSchema,
    AbstractProtobufEventWithSchema,
    SchemaRegistryMixin
)


class AbstractEventSerializer(ABC):

    def __init__(self, event: AbstractEvent, *args, **kwargs):
        self._event = event
        self._topic = event.topic
        super().__init__(*args, **kwargs)

    @property
    def payload(self):
        return self._event.payload

    @property
    @abstractmethod
    def serializer(self) -> Callable[[dict, SerializationContext], str]:
        raise NotImplementedError()

    def serialize(self, **kwargs):
        # TODO: consider abstracting this SerializationContext logic away
        # TODO: support Key ser?
        ctx = kwargs.pop('ctx', SerializationContext(self._topic, MessageField.VALUE))
        # TODO: error catching
        return self.serializer(self.payload, ctx)


class AbstractEventWithSchemaSerializer(SchemaRegistryMixin, AbstractEventSerializer, ABC):

    def __init__(self, event: AbstractEventWithSchema, *args, **kwargs):
        super().__init__(event, *args, **kwargs)
        self._event = event
        self._subject_name_strat = kwargs.pop('subject_name_strategy', None) or event.SUBJECT_NAME_STRATEGY
        self._auto_register_schema = True if get_config('ENV', 'dev') == 'dev' else False
        # TODO: add payload->schema validation

    @property
    def kafka_serializer_with_schema_config(self):
        # for use with avro, json serializers
        config = {
            'auto.register.schemas': self._auto_register_schema,
            # 'normalize.schemas': False,
            # 'use.latest.version': False,
        }
        if self._subject_name_strat is not None:
            config.update({'subject.name.strategy': self._subject_name_strat})
        return config

    def to_dict(self, obj, ctx):
        return obj


class GenericEventSerializer(AbstractEventSerializer):
    """Dummy serializer to return dict payload"""
    @property
    def serializer(self) -> Callable[[dict, SerializationContext], str]:
        return lambda payload, ctx: payload


class AvroEventSerializer(AbstractEventWithSchemaSerializer):
    def __init__(self, event: AbstractAvroEventWithSchema, *args, **kwargs):
        super().__init__(event, *args, **kwargs)
        self._event = event

    @property
    def serializer(self) -> Serializer:
        # init serializer, auto register in dev mode
        return AvroSerializer(
            self._event.kafka_schema_registry_client,
            schema_str=self._event.canonical_schema,
            conf=self.kafka_serializer_with_schema_config,
            to_dict=self.to_dict
        )


class JsonEventSerializer(AbstractEventWithSchemaSerializer):
    # TODO: implement integration
    pass


class ProtobufEventSerializer(AbstractEventWithSchemaSerializer):
    # TODO: implement integration
    pass


class EventSerializer:
    _serializer: Type[AbstractEventSerializer]

    def __init__(self, event: AbstractEvent, **conf):
        self._serializer = event.serializer

        if self._serializer is None:
            # map encoded events to respective serializers
            if isinstance(event, AbstractAvroEventWithSchema):
                self._serializer = AvroEventSerializer
            elif isinstance(event, AbstractJsonEventWithSchema):
                self._serializer = JsonEventSerializer
            elif isinstance(event, AbstractProtobufEventWithSchema):
                self._serializer = ProtobufEventSerializer
            else:
                self._serializer = GenericEventSerializer

        # instantiate serializer instance if there is one
        self.serializer = self._serializer(event, **conf)

    def serialize(self, **kwargs):
        # TODO: add error handling
        return self.serializer.serialize(**kwargs)


if __name__ == '__main__':
    class EgAvro(AbstractAvroEventWithSchema):
        topic = 'some-topic'

        @property
        def schema(self):
            return [
                {'name': 'id', 'type': 'string'},
                {'name': 'value', 'type': 'int'},
                {'name': 'oopsie', 'type': 'string', 'default': 'hello i am default'}
            ]

    a = EgAvro({'id': '1234', 'value': 2})
    ser = EventSerializer(a)
    print(ser.serialize())

    class Eg(AbstractEvent):
        topic = 'some-topic'


    a = Eg({'id': '1234', 'value': 2})
    ser = EventSerializer(a)
    print(ser.serialize())
