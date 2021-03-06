import logging
import subprocess
from time import sleep

import pytest
from aiohttp_json_rpc import RpcGenericServerDefinedError, RpcInvalidParamsError

from common.entities import App, Model
from mco.rpc import RPCClient
from microcore.entity.encoders import ProxyNativeEncoder

logger = logging.getLogger()


@pytest.fixture(scope='module')
async def rpc_client(event_loop) -> RPCClient:
    client = RPCClient('ws://localhost:8080', ProxyNativeEncoder(), loop=event_loop)
    yield client
    await client.close()


@pytest.fixture(scope='module')
def run_server() -> subprocess.Popen:
    logger.info('creating subprocess')
    p = subprocess.Popen(
        ['python3', '../src/apps/envmanager.py']
    )
    logger.info('run proc?')
    sleep(1)
    yield p
    p.terminate()
    logger.info('proc ret: %s', p.returncode)


@pytest.mark.asyncio
async def test_rpc_call_failed(rpc_client: RPCClient, run_server):
    with pytest.raises(RpcGenericServerDefinedError) as e:
        await rpc_client.create_app_instance(app=None, model=None, rpc_timeout=60)
    exc: RpcGenericServerDefinedError = e.value
    logger.info('e_msg: %s', exc.data)


@pytest.mark.asyncio
async def test_rpc_call_failed_invalid_args(rpc_client: RPCClient, run_server):
    with pytest.raises(RpcInvalidParamsError) as e:
        await rpc_client.create_app_instance(app=None)


@pytest.mark.asyncio
async def test_rpc_call_success(rpc_client: RPCClient, run_server):
    app = App(name='pytest_app', package='busybox:latest')
    model = Model(name='pytest_model')
    data = await rpc_client.create_app_instance(app=app, model=model, rpc_timeout=30)
    logger.info('returned: %s', data)

    data = await rpc_client.remove_app_instance(app, model, rpc_timeout=30)
    logger.info('returned: %s', data)
