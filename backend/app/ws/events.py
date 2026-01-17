"""WebSocket event type definitions per realtime-protocol-v1 spec."""

from enum import Enum


class EventType(str, Enum):
    """All WebSocket event types per spec section 4."""

    # System events (8)
    PING = "PING"
    PONG = "PONG"
    CONNECTION_STATE = "CONNECTION_STATE"
    ERROR = "ERROR"
    RECOVERY_REQUEST = "RECOVERY_REQUEST"
    RECOVERY_RESPONSE = "RECOVERY_RESPONSE"
    ANNOUNCEMENT = "ANNOUNCEMENT"  # 실시간 공지사항 브로드캐스트
    ROOM_FORCE_CLOSED = "ROOM_FORCE_CLOSED"  # 관리자에 의한 방 강제 종료

    # Lobby events (8)
    SUBSCRIBE_LOBBY = "SUBSCRIBE_LOBBY"
    UNSUBSCRIBE_LOBBY = "UNSUBSCRIBE_LOBBY"
    LOBBY_SNAPSHOT = "LOBBY_SNAPSHOT"
    LOBBY_UPDATE = "LOBBY_UPDATE"
    ROOM_CREATE_REQUEST = "ROOM_CREATE_REQUEST"
    ROOM_CREATE_RESULT = "ROOM_CREATE_RESULT"
    ROOM_JOIN_REQUEST = "ROOM_JOIN_REQUEST"
    ROOM_JOIN_RESULT = "ROOM_JOIN_RESULT"

    # Table events (16)
    SUBSCRIBE_TABLE = "SUBSCRIBE_TABLE"
    UNSUBSCRIBE_TABLE = "UNSUBSCRIBE_TABLE"
    TABLE_SNAPSHOT = "TABLE_SNAPSHOT"
    TABLE_STATE_UPDATE = "TABLE_STATE_UPDATE"
    TURN_PROMPT = "TURN_PROMPT"
    SEAT_REQUEST = "SEAT_REQUEST"
    SEAT_RESULT = "SEAT_RESULT"
    LEAVE_REQUEST = "LEAVE_REQUEST"
    LEAVE_RESULT = "LEAVE_RESULT"
    ADD_BOT_REQUEST = "ADD_BOT_REQUEST"
    ADD_BOT_RESULT = "ADD_BOT_RESULT"
    START_BOT_LOOP_REQUEST = "START_BOT_LOOP_REQUEST"
    START_BOT_LOOP_RESULT = "START_BOT_LOOP_RESULT"
    SIT_OUT_REQUEST = "SIT_OUT_REQUEST"
    SIT_IN_REQUEST = "SIT_IN_REQUEST"
    PLAYER_SIT_OUT = "PLAYER_SIT_OUT"
    PLAYER_SIT_IN = "PLAYER_SIT_IN"

    # Waitlist events (6)
    WAITLIST_JOIN_REQUEST = "WAITLIST_JOIN_REQUEST"  # 대기열 등록 요청
    WAITLIST_CANCEL_REQUEST = "WAITLIST_CANCEL_REQUEST"  # 대기열 취소 요청
    WAITLIST_JOINED = "WAITLIST_JOINED"  # 대기열 등록 완료
    WAITLIST_CANCELLED = "WAITLIST_CANCELLED"  # 대기열 취소됨/타임아웃
    WAITLIST_POSITION_CHANGED = "WAITLIST_POSITION_CHANGED"  # 대기열 위치 변경
    WAITLIST_SEAT_READY = "WAITLIST_SEAT_READY"  # 자리 비었음 - 착석 가능

    # Hand events (7)
    START_GAME = "START_GAME"
    GAME_STARTING = "GAME_STARTING"
    HAND_START = "HAND_START"
    HAND_STARTED = "HAND_STARTED"
    COMMUNITY_CARDS = "COMMUNITY_CARDS"
    REVEAL_CARDS = "REVEAL_CARDS"  # 클라이언트 → 서버: 카드 오픈 알림
    CARDS_REVEALED = "CARDS_REVEALED"  # 서버 → 클라이언트: 카드 오픈 브로드캐스트

    # Action events (6)
    ACTION_REQUEST = "ACTION_REQUEST"
    ACTION_RESULT = "ACTION_RESULT"
    SHOWDOWN_RESULT = "SHOWDOWN_RESULT"
    HAND_RESULT = "HAND_RESULT"
    TURN_CHANGED = "TURN_CHANGED"
    STACK_ZERO = "STACK_ZERO"  # 스택 0 시 리바이 모달용
    REBUY = "REBUY"  # 리바이 요청

    # Timer events
    TIMEOUT_FOLD = "TIMEOUT_FOLD"

    # Time Bank events
    TIME_BANK_REQUEST = "TIME_BANK_REQUEST"
    TIME_BANK_USED = "TIME_BANK_USED"

    # Chat events (2)
    CHAT_MESSAGE = "CHAT_MESSAGE"
    CHAT_HISTORY = "CHAT_HISTORY"


# Event direction mapping
# Note: PING/PONG are bidirectional for heartbeat mechanism
CLIENT_TO_SERVER_EVENTS = frozenset([
    EventType.PING,
    EventType.PONG,  # 클라이언트가 서버 PING에 응답
    EventType.SUBSCRIBE_LOBBY,
    EventType.UNSUBSCRIBE_LOBBY,
    EventType.ROOM_CREATE_REQUEST,
    EventType.ROOM_JOIN_REQUEST,
    EventType.SUBSCRIBE_TABLE,
    EventType.UNSUBSCRIBE_TABLE,
    EventType.SEAT_REQUEST,
    EventType.LEAVE_REQUEST,
    EventType.START_GAME,
    EventType.ACTION_REQUEST,
    EventType.CHAT_MESSAGE,
    EventType.RECOVERY_REQUEST,
    EventType.ADD_BOT_REQUEST,
    EventType.START_BOT_LOOP_REQUEST,
    EventType.SIT_OUT_REQUEST,
    EventType.SIT_IN_REQUEST,
    EventType.REBUY,  # 리바이 요청
    EventType.TIME_BANK_REQUEST,  # 타임 뱅크 요청
    EventType.REVEAL_CARDS,  # 카드 오픈 요청
    EventType.WAITLIST_JOIN_REQUEST,  # 대기열 등록 요청
    EventType.WAITLIST_CANCEL_REQUEST,  # 대기열 취소 요청
])

SERVER_TO_CLIENT_EVENTS = frozenset([
    EventType.PING,  # 서버가 클라이언트에게 하트비트 전송
    EventType.PONG,
    EventType.CONNECTION_STATE,
    EventType.ERROR,
    EventType.LOBBY_SNAPSHOT,
    EventType.LOBBY_UPDATE,
    EventType.ROOM_CREATE_RESULT,
    EventType.ROOM_JOIN_RESULT,
    EventType.TABLE_SNAPSHOT,
    EventType.TABLE_STATE_UPDATE,
    EventType.TURN_PROMPT,
    EventType.TURN_CHANGED,
    EventType.SEAT_RESULT,
    EventType.LEAVE_RESULT,
    EventType.GAME_STARTING,
    EventType.HAND_START,
    EventType.HAND_STARTED,
    EventType.COMMUNITY_CARDS,
    EventType.ACTION_RESULT,
    EventType.SHOWDOWN_RESULT,
    EventType.HAND_RESULT,
    EventType.CHAT_MESSAGE,
    EventType.CHAT_HISTORY,
    EventType.RECOVERY_RESPONSE,
    EventType.ADD_BOT_RESULT,
    EventType.STACK_ZERO,  # 리바이 모달용
    EventType.START_BOT_LOOP_RESULT,
    EventType.TIMEOUT_FOLD,
    EventType.PLAYER_SIT_OUT,
    EventType.PLAYER_SIT_IN,
    EventType.TIME_BANK_USED,  # 타임 뱅크 사용 결과
    EventType.CARDS_REVEALED,  # 카드 오픈 브로드캐스트
    EventType.ANNOUNCEMENT,  # 공지사항 브로드캐스트
    EventType.ROOM_FORCE_CLOSED,  # 방 강제 종료 알림
    EventType.WAITLIST_JOINED,  # 대기열 등록 완료
    EventType.WAITLIST_CANCELLED,  # 대기열 취소됨/타임아웃
    EventType.WAITLIST_POSITION_CHANGED,  # 대기열 위치 변경
    EventType.WAITLIST_SEAT_READY,  # 자리 비었음 - 착석 가능
])
