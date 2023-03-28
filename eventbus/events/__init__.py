import json
from abc import ABCMeta
from abc import abstractmethod
from copy import deepcopy
from datetime import datetime
from enum import Enum
from functools import cached_property
from inspect import isabstract
from typing import Union, Type
from uuid import UUID, uuid4

from confluent_kafka.schema_registry import (
    SchemaRegistryClient,
    topic_subject_name_strategy,
    topic_record_subject_name_strategy,
    record_subject_name_strategy
)
from fastavro.schema import SchemaParseException
from fastavro.schema import UnknownType
from fastavro.schema import parse_schema
from pydantic import BaseModel, Field, validator
from pydantic.error_wrappers import ValidationError

from eventbus import get_config
from eventbus.events.deserialize import AbstractEventDeserializer
from eventbus.events.serialize import AbstractEventSerializer


class EventCreationError(Exception):
    pass


class EventSchemaError(Exception):
    pass


class SubjectNameStrat(Enum):
    TopicSubjectName = 1
    TopicRecordSubjectName = 2
    RecordSubjectName = 3

    __callables__ = {
        TopicSubjectName: topic_subject_name_strategy,
        TopicRecordSubjectName: topic_record_subject_name_strategy,
        RecordSubjectName: record_subject_name_strategy
    }

    def __call__(self, ctx, record_name):
        return self.__callables__.get(self.value)(ctx, record_name)


class EventHeader(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('created_at', always=True)
    def validate(cls, dt):  # noqa
        return dt.isoformat()


class EventRegistryError(Exception):
    pass


class EventMeta(ABCMeta):
    _registry = {}

    def __new__(mcs, *args, **kwargs):
        cls = super().__new__(mcs, *args, **kwargs)
        name = getattr(cls, 'name', lambda: cls.__name__)()
        if not isabstract(cls):
            if name in mcs._registry:
                raise EventRegistryError(f'Event ({name}) already registered')
            mcs._registry[name] = cls
            print(mcs._registry)
        return cls

    @classmethod
    def get(mcs, name):
        if name not in mcs._registry:
            raise EventRegistryError(f'Event ({name}) not registered')
        return mcs._registry.get(name)


class EventRegistry(metaclass=EventMeta):
    pass


class AbstractEvent(EventRegistry):
    NAME: str = None

    _serializer: Type[AbstractEventSerializer]
    _deserializer: Type[AbstractEventDeserializer]

    _namespace = get_config('KAFKA_SCHEMA_REGISTRY_NAMESPACE', 'eventbus.events')

    def __init__(self, payload: Union[dict, str], headers: dict = None):
        self._payload = payload

        # construct header object
        try:
            self._headers = EventHeader(**headers) if headers else self.get_default_header()
        except ValidationError as e:
            raise EventCreationError(f'Failed to create event due to header validation error(s) - {e}')

    @property
    def serializer(self) -> Type[AbstractEventSerializer]:
        return self._serializer

    @property
    def deserializer(self) -> Type[AbstractEventDeserializer]:
        return self._deserializer

    @property
    @abstractmethod
    def topic(self) -> str:
        pass

    def __repr__(self):
        return {
            'headers': self.headers,
            'payload': self.payload
        }

    @classmethod
    def name(cls):
        return cls.NAME or cls.__name__

    @property
    def headers(self):
        return self._headers

    @property
    def payload(self):
        return self._payload

    def get_default_header(self):
        return EventHeader(name=self.name())


class SchemaRegistryMixin:
    @property
    def kafka_schema_registry_url(self):
        return get_config('KAFKA_SCHEMA_REGISTRY_CLUSTER_IP', 'http://localhost:8081')

    @property
    def kafka_schema_registry_client(self):
        config = dict(
            url=self.kafka_schema_registry_url
            # ** ssl, auth config
        )
        return SchemaRegistryClient(config)


class AbstractEventWithSchema(SchemaRegistryMixin, AbstractEvent):
    # Registrable events that can morph for serde
    DESCRIPTION = 'Eventbus Event'
    SUBJECT_NAME_STRATEGY: SubjectNameStrat = None  # default is 'topic-name' strat

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    @abstractmethod
    def schema(self):
        raise NotImplementedError()

    @property
    def _schema(self):
        return self.schema


class AbstractAvroEventWithSchema(AbstractEventWithSchema):
    DESCRIPTION = 'Avro Eventbus Event'

    @cached_property
    def _schema(self):
        # https://avro.apache.org/docs/current/spec.html#schemas
        schema = {
            'name': self.name(),
            'namespace': self._namespace,
            'doc': self.DESCRIPTION,
            'type': 'record',
            'fields': self.schema
        }
        try:
            return parse_schema(schema)
        except (UnknownType, SchemaParseException) as e:
            raise EventSchemaError(f'Error parsing schema: {e}')

    @cached_property
    def canonical_schema(self):
        # parse avro schema obj to canonical json string
        # https://avro.apache.org/docs/current/spec.html#schemas
        if self._schema is not None:
            schema = deepcopy(self._schema)
            schema.pop('__fastavro_parsed')
            schema.pop('__named_schemas')
            return json.dumps(schema)


class AbstractJsonEventWithSchema(AbstractEventWithSchema):
    # TODO: implement
    pass
    DESCRIPTION = 'Json Eventbus Event'


class AbstractProtobufEventWithSchema(AbstractEventWithSchema):
    # TODO: implement
    pass
    DESCRIPTION = 'Protobuf Eventbus Event'
