import hashlib
import mimetypes
import os

from aiohttp.web import Request, StreamResponse, HTTPNotFound, HTTPNotModified, Response

FIELD_FILENAME = '_filename'
FIELD_LENGTH = '_length'


def chunks(file_object, chunk_size=1024):
    """Lazy function (generator) to read a file piece by piece.
    Default chunk size: 1k."""
    while True:
        data = file_object.read(chunk_size)
        if not data:
            break
        yield data


async def accept_download(request: Request, path_attachment: str, path_tpl: str = '/opt/data/%s') -> StreamResponse:
    """

    :param request: request to extract files to
    :param path_attachment: filename of attachment
    :param path_tpl: %template of file destination ( ex.: /opt/data/%s )
    """
    # ensure dir exists
    os.makedirs(os.path.dirname(path_tpl), exist_ok=True)

    filename = os.path.basename(path_attachment)
    filepath = path_attachment
    _, ext = os.path.splitext(filepath)
    etag = hashlib.sha1(filename.encode('utf-8')).hexdigest()

    if not os.path.exists(filepath):
        raise HTTPNotFound()

    if 'If-None-Match' in request.headers:
        raise HTTPNotModified(headers={
            'ETag': etag
        })

    stat = os.stat(filepath)

    if request.method == 'HEAD':
        resp = Response()
    else:
        resp = StreamResponse()

    resp.headers['Content-Type'] = mimetypes.types_map.get(ext, 'application/octet-stream')
    resp.headers['ETag'] = etag
    # resp.headers['Cache-Control'] = 'max-age=31536000'
    resp.headers['Cache-Control'] = 'no-cache'
    disposition = 'filename="{}"'.format(filename[36:])
    if 'text' not in resp.content_type and 'json' not in resp.content_type:
        disposition = 'attachment; ' + disposition
    resp.headers['Content-Disposition'] = disposition
    resp.content_length = stat.st_size
    resp.last_modified = stat.st_mtime

    if request.method == 'HEAD':
        return resp

    await resp.prepare(request)
    with open(filepath, 'rb') as f:
        for chunk in chunks(f):
            await resp.write(chunk)
            await resp.drain()

    await resp.write_eof()
    resp.force_close()
    return resp
