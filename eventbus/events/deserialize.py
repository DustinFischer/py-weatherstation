from abc import ABC
from abc import abstractmethod
from typing import Callable, Type, Union

from confluent_kafka.schema_registry.avro import AvroDeserializer
# from confluent_kafka.schema_registry.json_schema import JSONDeserializer
from confluent_kafka.serialization import Deserializer, StringDeserializer
from confluent_kafka.serialization import MessageField
from confluent_kafka.serialization import SerializationContext

from eventbus import get_config
from eventbus.events import (
    AbstractEvent,
    AbstractAvroEventWithSchema,
    AbstractJsonEventWithSchema,
    AbstractProtobufEventWithSchema,
    SchemaRegistryMixin
)
from eventbus.events.serialize import EventSerializer


class AbstractEventDeserializer(ABC):
    def __init__(self, event: AbstractEvent, *args, **kwargs):
        self._event = event
        self._topic = event.topic
        super().__init__(*args, **kwargs)

    @property
    def payload(self):
        return self._event.payload

    @property
    @abstractmethod
    def deserializer(self) -> Callable[[str, SerializationContext], Union[dict, object]]:
        raise NotImplementedError()

    def deserialize(self, **kwargs):
        # TODO: consider abstracting this SerializationContext logic away
        # TODO: support Key deser?
        ctx = kwargs.pop('ctx', SerializationContext(self._topic, MessageField.VALUE))
        # TODO: error catching
        return self.deserializer(self.payload, ctx)


class AbstractEventWithSchemaDeserializer(SchemaRegistryMixin, AbstractEventDeserializer, ABC):

    def from_dict(self, data, ctx):
        return data


class GenericEventDeserializer(AbstractEventDeserializer):
    """Dummy serializer to return dict payload"""

    @property
    def deserializer(self) -> Callable[[str, SerializationContext], str]:
        return StringDeserializer()  # noqa


class EventDeserializer:
    _deserializer: Type[AbstractEventDeserializer] = None

    def __init__(self, event: AbstractEvent, **conf):
        self._deserializer = event.deserializer

        if self._deserializer is None:
            # map encoded events to respective serializers
            if isinstance(event, AbstractAvroEventWithSchema):
                self._deserializer = AvroEventDeserializer
            elif isinstance(event, AbstractJsonEventWithSchema):
                self._deserializer = JsonEventDeserializer
            elif isinstance(event, AbstractProtobufEventWithSchema):
                self._deserializer = ProtobufEventDeserializer
            else:
                self._deserializer = GenericEventDeserializer

        # instantiate serializer instance if there is one
        self.deserializer = self._deserializer(event, **conf)

    def deserialize(self, **kwargs):
        # TODO: Add validation and raise_on_error
        # TODO: add error handling
        return self.deserializer.deserialize(**kwargs)


class AvroEventDeserializer(AbstractEventWithSchemaDeserializer):
    def __init__(self, event: AbstractAvroEventWithSchema, *args, **kwargs):
        super().__init__(event, *args, **kwargs)
        self._event = event

    @property
    def deserializer(self) -> Deserializer:
        # init deserializer
        return AvroDeserializer(
            self._event.kafka_schema_registry_client,
            schema_str=self._event.canonical_schema,
            from_dict=self.from_dict
        )


class JsonEventDeserializer(AbstractEventWithSchemaDeserializer):
    def __init__(self, event: AbstractJsonEventWithSchema, *args, **kwargs):
        super().__init__(event, *args, **kwargs)
        self._event = event

    # @property
    # def deserializer(self) -> Deserializer:
    #     # init deserializer
    #     return JSONDeserializer(
    #         schema_str='',
    #         from_dict=self.from_dict
    #     )


class ProtobufEventDeserializer(AbstractEventWithSchemaDeserializer):
    # TODO: implement integration
    pass


if __name__ == '__main__':
    from confluent_kafka.schema_registry import SchemaRegistryClient


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
    schema_str = a.canonical_schema
    print(schema_str)

    schema_registry_client = SchemaRegistryClient(
        dict(url=get_config('KAFKA_SCHEMA_REGISTRY_CLUSTER_IP', 'http://localhost:8081')))
    ser = EventSerializer(a)
    msg = ser.serialize()

    print(msg)


    class EgAvro2(AbstractAvroEventWithSchema):
        topic = 'some-topic'

        @property
        def schema(self):
            return [
                {'name': 'id', 'type': 'string'},
                {'name': 'value', 'type': 'int'},
                # {'name': 'oopsie', 'type': 'string', 'default': 'hello i am default'}
            ]


    a = EgAvro(msg)
    schema_str = a.canonical_schema

    de = EventDeserializer(a)

    payload = de.deserialize()
    print()
    print(payload)
