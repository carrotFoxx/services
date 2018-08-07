import attr


@attr.s(auto_attribs=True)
class InstanceDefinition:
    uid: str
    image: str
    attachments: dict = attr.Factory(dict)
    labels: dict = attr.Factory(dict)
    restart_policy: str = 'always'
