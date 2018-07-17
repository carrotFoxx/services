from common.entities import App
from common.versioning import VersionedAPI


class ApplicationManagerAPI(VersionedAPI):
    prefix = '/applications'
    entity_type = App
