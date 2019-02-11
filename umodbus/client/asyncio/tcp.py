"""
"""
import asyncio
from logzero import logger
from async_timeout import timeout as async_timeout
from umodbus.client.tcp import (
    raise_for_exception_adu,
    expected_response_pdu_size_from_request_pdu,
    parse_response_adu
)
import umodbus.client.tcp as tcp


async def recv_exactly(loop, sock, size, timeout):
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
        logger.debug(f'awaiting {size - recv_bytes}')
        async with async_timeout(timeout):
            chunk = await loop.sock_recv(sock, size - recv_bytes)
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

async def send_message(adu, sock, loop=None, timeout=None):
    """ Send ADU over socket to to server and return parsed response.

    :param adu: Request ADU.
    :param sock: Socket instance.
    :return: Parsed response from server.
    """
    loop = loop or asyncio.get_event_loop()
    logger.debug(f'sending packet {adu!r}')
    status = await loop.sock_sendall(sock, adu)

    # Check exception ADU (which is shorter than all other responses) first.
    exception_adu_size = 9
    logger.debug('reading response header')
    response_error_adu = await recv_exactly(loop, sock, exception_adu_size, timeout)
    raise_for_exception_adu(response_error_adu)
    expected_response_size = \
        expected_response_pdu_size_from_request_pdu(adu[7:]) + 7
    logger.debug(f'reading response data ({expected_response_size} bytes)')
    response_remainder = await recv_exactly(loop, sock,
                                            expected_response_size - exception_adu_size,
                                            timeout)
    response = response_error_adu + response_remainder
    logger.debug(f'parsing response {response!r}')

    parsed = parse_response_adu(response, adu)
    logger.debug('done')
    return parsed
