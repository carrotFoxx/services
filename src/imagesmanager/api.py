import logging

from common.entities import Image
from common.versioning import VersionedAPI

logger = logging.getLogger(__name__)


class ImageManagerAPI(VersionedAPI):
    prefix = '/images'
    entity_type = Image
