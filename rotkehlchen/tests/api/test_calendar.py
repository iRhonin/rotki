from http import HTTPStatus
import pytest
import requests

from rotkehlchen.api.server import APIServer
from rotkehlchen.chain.ethereum.modules.curve.constants import CPT_CURVE
from rotkehlchen.chain.ethereum.modules.ens.constants import CPT_ENS
from rotkehlchen.tests.utils.api import (
    api_url_for,
    assert_error_response,
    assert_proper_response,
    assert_proper_response_with_result,
)
from rotkehlchen.types import ChecksumEvmAddress, SupportedBlockchain


@pytest.mark.parametrize('have_decoders', [True])
@pytest.mark.parametrize('ethereum_accounts', [[
    '0xc37b40ABdB939635068d3c5f13E7faF686F03B65',
    '0x2B888954421b424C5D3D9Ce9bB67c9bD47537d12',
]])
@pytest.mark.parametrize('gnosis_accounts', [[
    '0x2B888954421b424C5D3D9Ce9bB67c9bD47537d12',
]])
def test_basic_calendar_operations(
        rotkehlchen_api_server: APIServer,
        ethereum_accounts: list[ChecksumEvmAddress],
):
    database = rotkehlchen_api_server.rest_api.rotkehlchen.data.db
    crv_event = (2, 'CRV unlock', 'Unlock date for CRV', CPT_CURVE, ethereum_accounts[1], 1851422011)  # noqa: E501

    # save 2 entries in the db
    response = requests.put(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'timestamp': 1869737344,
            'name': 'ENS renewal',
            'description': 'Renew yabir.eth',
            'counterparty': CPT_ENS,
            'address': ethereum_accounts[0],
            'blockchain': SupportedBlockchain.ETHEREUM.serialize(),
        },
    )

    data = assert_proper_response_with_result(response)
    assert data['entry_id'] == 1

    response = requests.put(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'name': crv_event[1],
            'description': crv_event[2],
            'counterparty': crv_event[3],
            'address': crv_event[4],
            'blockchain': SupportedBlockchain.ETHEREUM.serialize(),
            'timestamp': crv_event[5],
        },
    )
    data = assert_proper_response_with_result(response)
    assert data['entry_id'] == 2

    with database.conn.read_ctx() as cursor:
        db_rows = cursor.execute(
            'SELECT identifier, name, description, counterparty, address, timestamp FROM calendar',
        ).fetchall()
        assert db_rows == [
            (1, 'ENS renewal', 'Renew yabir.eth', CPT_ENS, ethereum_accounts[0], 1869737344),
            crv_event,
        ]

    # update the ens entry
    response = requests.patch(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'identifier': 1,
            'timestamp': 1977652411,
            'name': 'ENS renewal',
            'description': 'Renew yabir.eth extended',
            'counterparty': CPT_ENS,
            'address': ethereum_accounts[0],
            'blockchain': SupportedBlockchain.ETHEREUM.serialize(),
        },
    )
    with database.conn.read_ctx() as cursor:
        db_rows = cursor.execute(
            'SELECT identifier, name, description, counterparty, address, timestamp FROM calendar',
        ).fetchall()
        assert db_rows == [
            (1, 'ENS renewal', 'Renew yabir.eth extended', CPT_ENS, ethereum_accounts[0], 1977652411),  # noqa: E501
            crv_event,
        ]

    # query calendar events
    ens_json_event = {
        'identifier': 1,
        'name': 'ENS renewal',
        'description':
        'Renew yabir.eth extended',
        'counterparty': CPT_ENS,
        'timestamp': 1977652411,
        'address': ethereum_accounts[0],
        'blockchain': 'eth',
    }
    curve_json_event = {
        'identifier': 2,
        'name': 'CRV unlock',
        'description': 'Unlock date for CRV',
        'counterparty': CPT_CURVE,
        'timestamp': 1851422011,
        'address': ethereum_accounts[1],
        'blockchain': 'eth',
    }
    future_ts = {'to_timestamp': 3479391239}  # timestamp enough in the future to return all the events  # noqa: E501
    response = requests.post(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json=future_ts,
    )
    assert assert_proper_response_with_result(response) == {
        'entries': [ens_json_event, curve_json_event],
        'entries_found': 2,
        'entries_total': 2,
        'entries_limit': -1,
    }

    # query with filter on timestamp
    response = requests.post(
        url=api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={'from_timestamp': 1977652400, 'to_timestamp': 1977652511},
    )
    assert assert_proper_response_with_result(response) == {
        'entries': [ens_json_event],
        'entries_found': 1,
        'entries_total': 2,
        'entries_limit': -1,
    }

    # query with addresses
    response = requests.post(
        url=api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'accounts': [{'address': ethereum_accounts[0], 'blockchain': 'eth'}],
        } | future_ts,
    )
    assert assert_proper_response_with_result(response) == {
        'entries': [ens_json_event],
        'entries_found': 1,
        'entries_total': 2,
        'entries_limit': -1,
    }

    # query with counterparty
    response = requests.post(
        url=api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={'counterparty': CPT_CURVE} | future_ts,
    )
    assert assert_proper_response_with_result(response) == {
        'entries': [curve_json_event],
        'entries_found': 1,
        'entries_total': 2,
        'entries_limit': -1,
    }

    # query with name substring
    response = requests.post(
        url=api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={'name': 'renewal'} | future_ts,
    )
    assert assert_proper_response_with_result(response) == {
        'entries': [ens_json_event],
        'entries_found': 1,
        'entries_total': 2,
        'entries_limit': -1,
    }

    # query with description substring
    response = requests.post(
        url=api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={'name': 'Unlock'} | future_ts,
    )
    assert assert_proper_response_with_result(response) == {
        'entries': [curve_json_event],
        'entries_found': 1,
        'entries_total': 2,
        'entries_limit': -1,
    }

    # delete the ens entry. The crv entry should be kept
    response = requests.delete(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={'identifier': 1},
    )
    assert_proper_response(response)
    with database.conn.read_ctx() as cursor:
        db_rows = cursor.execute(
            'SELECT identifier, name, description, counterparty, '
            'address, timestamp FROM calendar',
        ).fetchall()
        assert db_rows == [crv_event]

    # add an event to gnosis and filter only by address and not chain
    response = requests.put(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'name': 'gnosis event',
            'description': crv_event[2],
            'counterparty': crv_event[3],
            'address': crv_event[4],
            'blockchain': SupportedBlockchain.GNOSIS.serialize(),
            'timestamp': crv_event[5],
        },
    )
    response = requests.post(
        url=api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={'accounts': [{'address': crv_event[4]}]} | future_ts,
    )
    result = assert_proper_response_with_result(response)['entries']
    assert result[0]['blockchain'] == SupportedBlockchain.ETHEREUM.serialize()
    assert result[1]['blockchain'] == SupportedBlockchain.GNOSIS.serialize()


@pytest.mark.parametrize('have_decoders', [True])
@pytest.mark.parametrize('ethereum_accounts', [['0xc37b40ABdB939635068d3c5f13E7faF686F03B65']])
def test_validation_calendar(
        rotkehlchen_api_server: APIServer,
        ethereum_accounts: list[ChecksumEvmAddress],
):
    database = rotkehlchen_api_server.rest_api.rotkehlchen.data.db

    # test creating event without address
    response = requests.put(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'timestamp': 1869737344,
            'name': 'ENS renewal',
            'description': 'Renew yabir.eth',
            'counterparty': CPT_ENS,
        },
    )
    assert_proper_response(response)
    with database.conn.read_ctx() as cursor:
        assert database.get_entries_count(cursor=cursor, entries_table='calendar') == 1

    # test creating event without a valid counterparty
    response = requests.put(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'timestamp': 1869737344,
            'name': 'ENS renewal',
            'description': 'Renew yabir.eth',
            'counterparty': 'BAD COUNTERPARTY',
        },
    )
    assert_error_response(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        contained_in_msg='Unknown counterparty',
    )

    # test providing only address
    response = requests.put(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'timestamp': 1869737344,
            'name': 'ENS renewal',
            'description': 'Renew yabir.eth',
            'address': ethereum_accounts[0],
        },
    )
    assert_error_response(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        contained_in_msg='If any of address or blockchain is provided both need to be provided',
    )

    # provide invalid bitcoin address
    response = requests.put(
        api_url_for(rotkehlchen_api_server, 'calendarresource'),
        json={
            'timestamp': 1869737344,
            'name': 'ENS renewal',
            'description': 'Renew yabir.eth',
            'address': ethereum_accounts[0],
            'blockchain': SupportedBlockchain.BITCOIN.serialize(),
        },
    )
    assert_error_response(
        response=response,
        status_code=HTTPStatus.BAD_REQUEST,
        contained_in_msg='is not a bitcoin address',
    )
