"""
"""
import asyncio
from logzero import logger
from async_timeout import timeout as aio_timeout
from umodbus.client.tcp import (
    raise_for_exception_adu,
    expected_response_pdu_size_from_request_pdu,
    parse_response_adu
)
import umodbus.client.tcp as tcp

DEBUG = False
def debug(*args, **kw):
    if DEBUG:
        logger.debug(*args, **kw)

async def recv_exactly(reader, size, timeout):
    """ Use the function to read and return exactly number of bytes desired.

    https://docs.python.org/3/howto/sockets.html#socket-programming-howto for
    more information about why this is necessary.

    :param recv_fn: Function that can return up to given bytes
        (i.e. socket.recv, file.read)
    :param size: Number of bytes to read.
    :return: Byte string with length size.
    :raises ValueError: Could not receive enough data (usually timeout).
    """
    recv_bytes = 0
    chunks = []
    while recv_bytes < size:
        debug(f'awaiting {size - recv_bytes}')
        async with aio_timeout(timeout):
            chunk = await reader.read(size - recv_bytes)
        if len(chunk) == 0:  # when closed or empty
            break
        recv_bytes += len(chunk)
        chunks.append(chunk)

    response = b''.join(chunks)

    if len(response) == 0:
        raise RuntimeError('Connection Lost!')

    if len(response) != size:
        raise ValueError  # FIXME

    return response

async def send_message(adu, reader, writer, timeout=None):
    """ Send ADU over socket to to server and return parsed response.

    :param adu: Request ADU.
    :param sock: Socket instance.
    :return: Parsed response from server.
    """
    debug(f'sending packet {adu!r}')
    debug(f'reader: {reader}')
    debug(f'writer: {writer}')
    debug(f'timeout: {timeout}')
    status = writer.write(adu)
    await writer.drain()
    debug(f'status: {status}')

    # Check exception ADU (which is shorter than all other responses) first.
    exception_adu_size = 9
    debug('reading response header')
    async with aio_timeout(timeout):
        response_error_adu = await reader.readexactly(exception_adu_size)
    raise_for_exception_adu(response_error_adu)
    expected_response_size = \
            expected_response_pdu_size_from_request_pdu(adu[7:]) + 7
    debug(f'reading response data ({expected_response_size} bytes)')
    async with aio_timeout(timeout):
        response_remainder = await reader.readexactly(expected_response_size - exception_adu_size)
    response = response_error_adu + response_remainder
    debug(f'parsing response {response!r}')

    parsed = parse_response_adu(response, adu)
    debug('done')
    return parsed
