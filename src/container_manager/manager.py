import hashlib

from common.entities import App, Model
from container_manager.definition import InstanceDefinition
from container_manager.docker import DockerProvider


class ContainerManager:
    def __init__(self, provider: DockerProvider) -> None:
        self.provider = provider

    @staticmethod
    def _get_hashed_id(*args) -> str:
        hash_func = hashlib.sha1()
        for x in args:
            hash_func.update(x)
        return hash_func.hexdigest()

    def create_app_instance_definition(self, app: App, model: Model):
        image = app.package
        volume_data = model.attachment
        instance_id = self._get_hashed_id(app.uid, app.version, model.uid, model.version)

        return InstanceDefinition(
            uid=instance_id,
            image=image,
            attachments={
                '/var/model': volume_data
            },
            labels={
                'app_id': app.uid,
                'app_name': app.name,
                'app_ver': app.version,
                'model_id': model.uid,
                'model_name': model.name,
                'model_ver': model.version
            }
        )

    async def create_app_instance(self, app: App, model: Model):
        await self.provider.launch_instance(self.create_app_instance_definition(app, model))

    async def remove_app_instance(self, app: App, model: Model):
        await self.provider.stop_instance(self.create_app_instance_definition(app, model))
