"""
Free Fire Protocol Command IDs & Packet Opcodes
Maps binary command integers to human-readable network packet types.
Consolidated from newbrsup/message_ids.py and UDP_LEAKED_BY_SAITO/message_ids.py.
"""

class Opcodes:
    CMD_LOGIN_REQ        = 0x0001
    CMD_LOGIN_RESP       = 0x0002
    CMD_LOGOUT_REQ       = 0x0003
    CMD_TOKEN_REFRESH    = 0x0004
    CMD_HEARTBEAT        = 0x0005
    CMD_HEARTBEAT_ACK    = 0x0006
    CMD_ENTER_LOBBY      = 0x0032
    CMD_LOBBY_STATE      = 0x0033
    CMD_CREATE_ROOM      = 0x0064
    CMD_JOIN_ROOM        = 0x0065
    CMD_LEAVE_ROOM       = 0x0066
    CMD_TEAM_READY       = 0x0067
    CMD_TEAM_SLOT_UPDATE = 0x0068
    CMD_START_MATCH      = 0x00C8
    CMD_MATCH_STATUS     = 0x00C9
    CMD_CANCEL_MATCH     = 0x00CA
    CMD_MATCH_FOUND      = 0x00CB
    CMD_ACCEPT_MATCH     = 0x00CC
    CMD_GAME_SERVER_AUTH = 0x012C
    CMD_PLAYER_STATS     = 0x012D
    CMD_ERROR_NOTICE     = 0x01F4
