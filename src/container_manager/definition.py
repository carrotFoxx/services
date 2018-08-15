import attr

from mco.entities import RegisteredEntityJSONEncoder


@attr.s(auto_attribs=True)
class InstanceDefinition:
    uid: str
    image: str
    attachments: dict = attr.Factory(dict)
    environment: dict = attr.Factory(dict)
    labels: dict = attr.Factory(dict)
    restart_policy: str = 'always'


@attr.s(auto_attribs=True)
class Instance:
    uid: str
    name: str
    state: str


class InstanceJsonEncoder(RegisteredEntityJSONEncoder):
    entity_type = Instance
