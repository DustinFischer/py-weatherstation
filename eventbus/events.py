from eventbus.events import AbstractAvroEventWithSchema


class DummyAvroEvent(AbstractAvroEventWithSchema):
    topic = 'other-topic'

    @property
    def schema(self):
        return [
            {'name': 'id', 'type': 'string'},
            {'name': 'value', 'type': 'int'},
        ]
