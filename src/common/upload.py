import mimetypes
import os
from typing import Union
from uuid import uuid4

from aiohttp import BodyPartReader, MultipartReader, StreamReader, hdrs
from aiohttp.web import Request

FIELD_FILENAME = '_filename'
FIELD_LENGTH = '_length'


async def accept_upload(request: Request, path_tpl: str = '/opt/data/%s'):
    """

    :param request: request to extract files from
    :param path_tpl: %template of file destination ( ex.: /opt/data/%s )
    """
    # ensure dir exists
    os.makedirs(os.path.dirname(path_tpl), exist_ok=True)

    metadata = {}
    if request.content_type.startswith('multipart/'):
        reader = await request.multipart()
        async for part in reader:  # type: Union[BodyPartReader,MultipartReader]
            if part.headers.get(hdrs.CONTENT_TYPE) == 'application/json':
                metadata = await part.json()
                continue
            if part.filename is not None:
                metadata[hdrs.CONTENT_TYPE] = part.headers.get(hdrs.CONTENT_TYPE) or 'application/binary'
                metadata[FIELD_FILENAME] = filename = path_tpl % str(uuid4()) + part.filename

                length = 0
                with open(filename, mode='xb') as file:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        length += len(chunk)
                        file.write(chunk)
                metadata[FIELD_LENGTH] = length
                continue
    else:  # try accept raw stream as file
        reader: StreamReader = request.content
        metadata[hdrs.CONTENT_TYPE] = request.content_type
        ext = mimetypes.guess_extension(metadata[hdrs.CONTENT_TYPE]) or '.ukn'
        metadata[FIELD_FILENAME] = filename = path_tpl % str(uuid4()) + ext
        length = 0
        with open(filename, mode='xb') as file:
            async for chunk in reader.iter_chunked(BodyPartReader.chunk_size):
                length += len(chunk)
                file.write(chunk)
            metadata[FIELD_LENGTH] = length

    return metadata
