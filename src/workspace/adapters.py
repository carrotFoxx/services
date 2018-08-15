from common.entities import Workspace, WorkspaceStorageEncoder
from config import MONGO_DB
from microcore.entity.encoders import ProxyNativeEncoder
from microcore.storage.mongo import SimpleMongoStorageAdapter

_workspace_encoder = ProxyNativeEncoder(
    force_type_mapping={
        Workspace: WorkspaceStorageEncoder()
    }
)


class WorkspaceMongoStorageAdapter(SimpleMongoStorageAdapter):
    def __init__(self) -> None:
        super().__init__(MONGO_DB.workspaces, _workspace_encoder)

    def save(self, entity: Workspace):
        entity.date_update()
        return super().save(entity)

    def patch(self, entity: Workspace, *args, **kwargs):
        entity.date_update()
        return super().patch(entity, *args, **kwargs)
