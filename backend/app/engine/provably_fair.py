"""
Provably Fair Random Number Generation.

표준 암호학적 보안 난수 생성(CSPRNG)을 사용한
검증 가능한 공정성 시스템.

핵심 원리:
─────────────────────────────────────────────────────────────────

1. 서버 시드 (Server Seed):
   - secrets.token_hex(32)로 256비트 무작위 값 생성
   - 핸드 시작 전 해시만 공개 (SHA-256)
   - 핸드 종료 후 원본 공개

2. 클라이언트 시드 (Client Seed):
   - 플레이어가 제공하거나 자동 생성
   - 서버가 조작할 수 없음을 보장

3. 조합 시드 (Combined Seed):
   - SHA256(server_seed + client_seed + nonce)
   - 이 값으로 결정론적 셔플 수행

4. 검증:
   - 핸드 종료 후 모든 시드 공개
   - 누구나 동일한 결과 재현 가능

─────────────────────────────────────────────────────────────────
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class FairSeed:
    """Provably fair seed pair."""

    server_seed: str  # 핸드 종료 전까지 비공개
    server_seed_hash: str  # 핸드 시작 시 공개 (사전 약속)
    client_seed: str  # 유저가 제공 또는 자동 생성
    nonce: int  # 핸드 번호 (동일 시드로 복제 방지)

    def to_dict(self) -> dict:
        return {
            "server_seed_hash": self.server_seed_hash,
            "client_seed": self.client_seed,
            "nonce": self.nonce,
        }

    def to_revealed_dict(self) -> dict:
        """핸드 종료 후 공개용."""
        return {
            "server_seed": self.server_seed,
            "server_seed_hash": self.server_seed_hash,
            "client_seed": self.client_seed,
            "nonce": self.nonce,
        }


@dataclass
class HandFairnessProof:
    """핸드 공정성 증명 데이터."""

    proof_id: str = field(default_factory=lambda: str(uuid4()))
    hand_id: str = ""
    room_id: str = ""

    # 시드 정보
    server_seed_hash: str = ""  # 핸드 시작 시 공개됨
    server_seed: str = ""  # 핸드 종료 후 공개됨 (None until revealed)
    client_seed: str = ""
    nonce: int = 0

    # 결과 정보
    deck_order_hash: str = ""  # 셔플된 덱 순서의 해시 (검증용)
    created_at: datetime = field(default_factory=datetime.utcnow)
    revealed_at: Optional[datetime] = None

    @property
    def is_revealed(self) -> bool:
        return self.server_seed != ""

    @property
    def verification_url(self) -> str:
        return f"/api/v1/verify/{self.hand_id}"

    def to_public_dict(self) -> dict:
        """핸드 진행 중 공개 정보."""
        return {
            "proof_id": self.proof_id,
            "hand_id": self.hand_id,
            "server_seed_hash": self.server_seed_hash,
            "client_seed": self.client_seed,
            "nonce": self.nonce,
            "created_at": self.created_at.isoformat(),
            "verification_url": self.verification_url,
        }

    def to_revealed_dict(self) -> dict:
        """핸드 종료 후 전체 공개 정보."""
        return {
            "proof_id": self.proof_id,
            "hand_id": self.hand_id,
            "server_seed": self.server_seed,
            "server_seed_hash": self.server_seed_hash,
            "client_seed": self.client_seed,
            "nonce": self.nonce,
            "deck_order_hash": self.deck_order_hash,
            "created_at": self.created_at.isoformat(),
            "revealed_at": self.revealed_at.isoformat() if self.revealed_at else None,
            "verification_url": self.verification_url,
        }


class ProvablyFairEngine:
    """
    검증 가능한 공정성 엔진.

    모든 카드 셔플이 사전에 결정되고,
    사후에 누구나 검증할 수 있습니다.
    """

    # 표준 52장 카드 덱 (0-51 인덱스)
    DECK_SIZE = 52

    # 카드 인덱스 → 카드 문자열 변환
    SUITS = ["c", "d", "h", "s"]  # clubs, diamonds, hearts, spades
    RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]

    @staticmethod
    def generate_server_seed() -> tuple[str, str]:
        """
        CSPRNG로 서버 시드 생성.

        Returns:
            (server_seed, server_seed_hash)
        """
        # secrets.token_hex는 os.urandom을 사용 (CSPRNG)
        server_seed = secrets.token_hex(32)  # 256-bit
        server_seed_hash = hashlib.sha256(server_seed.encode()).hexdigest()
        return server_seed, server_seed_hash

    @staticmethod
    def generate_client_seed() -> str:
        """
        클라이언트 시드 자동 생성.

        Returns:
            client_seed (64 hex chars)
        """
        return secrets.token_hex(16)  # 128-bit

    @staticmethod
    def combine_seeds(server_seed: str, client_seed: str, nonce: int) -> str:
        """
        시드 조합.

        Args:
            server_seed: 서버 시드
            client_seed: 클라이언트 시드
            nonce: 핸드 번호 (동일 시드 쌍으로 여러 핸드 가능)

        Returns:
            Combined seed (64 hex chars)
        """
        combined = f"{server_seed}:{client_seed}:{nonce}"
        return hashlib.sha256(combined.encode()).hexdigest()

    @staticmethod
    def shuffle_deck(combined_seed: str) -> list[int]:
        """
        결정론적 카드 셔플 (Fisher-Yates).

        Args:
            combined_seed: 256-bit hex seed

        Returns:
            52개 카드 인덱스 리스트 (0-51)

        알고리즘:
        - Fisher-Yates shuffle
        - O(n) 시간 복잡도
        - 균등 분포 보장
        """
        import random

        # seed를 정수로 변환하여 PRNG 시드로 사용
        seed_int = int(combined_seed, 16)
        rng = random.Random(seed_int)

        deck = list(range(ProvablyFairEngine.DECK_SIZE))

        # Fisher-Yates shuffle (O(n), 균등 분포 보장)
        for i in range(51, 0, -1):
            j = rng.randint(0, i)
            deck[i], deck[j] = deck[j], deck[i]

        return deck

    @staticmethod
    def deck_order_to_hash(deck: list[int]) -> str:
        """
        덱 순서의 해시 생성 (검증용).

        Args:
            deck: 카드 인덱스 리스트

        Returns:
            SHA-256 hash of deck order
        """
        deck_str = ",".join(str(c) for c in deck)
        return hashlib.sha256(deck_str.encode()).hexdigest()

    @staticmethod
    def index_to_card(index: int) -> str:
        """
        카드 인덱스를 카드 문자열로 변환.

        Args:
            index: 0-51

        Returns:
            카드 문자열 (예: "As", "2c", "Kh")
        """
        suit = ProvablyFairEngine.SUITS[index // 13]
        rank = ProvablyFairEngine.RANKS[index % 13]
        return f"{rank}{suit}"

    @staticmethod
    def card_to_index(card: str) -> int:
        """
        카드 문자열을 인덱스로 변환.

        Args:
            card: 카드 문자열 (예: "As", "2c")

        Returns:
            0-51 인덱스
        """
        rank = card[0]
        suit = card[1].lower()

        suit_idx = ProvablyFairEngine.SUITS.index(suit)
        rank_idx = ProvablyFairEngine.RANKS.index(rank)

        return suit_idx * 13 + rank_idx

    @staticmethod
    def deck_to_cards(deck: list[int]) -> list[str]:
        """
        덱 인덱스 리스트를 카드 문자열 리스트로 변환.

        Args:
            deck: 카드 인덱스 리스트

        Returns:
            카드 문자열 리스트
        """
        return [ProvablyFairEngine.index_to_card(i) for i in deck]

    @staticmethod
    def verify_fairness(
        server_seed: str,
        server_seed_hash: str,
        client_seed: str,
        nonce: int,
        expected_deck_hash: str,
    ) -> tuple[bool, str | None]:
        """
        클라이언트 측 공정성 검증.

        Args:
            server_seed: 핸드 종료 후 공개된 서버 시드
            server_seed_hash: 핸드 시작 시 공개된 해시
            client_seed: 클라이언트 시드
            nonce: 핸드 번호
            expected_deck_hash: 예상 덱 순서 해시

        Returns:
            (success, error_message)
        """
        # 1. 서버 시드 해시 검증
        computed_hash = hashlib.sha256(server_seed.encode()).hexdigest()
        if computed_hash != server_seed_hash:
            return False, "Server seed hash mismatch"

        # 2. 동일한 덱 순서 재현 가능 확인
        combined = ProvablyFairEngine.combine_seeds(server_seed, client_seed, nonce)
        computed_deck = ProvablyFairEngine.shuffle_deck(combined)
        computed_deck_hash = ProvablyFairEngine.deck_order_to_hash(computed_deck)

        if computed_deck_hash != expected_deck_hash:
            return False, "Deck order hash mismatch"

        return True, None

    @staticmethod
    def create_hand_proof(
        hand_id: str,
        room_id: str,
        client_seed: str | None = None,
        nonce: int = 1,
    ) -> tuple[HandFairnessProof, list[int]]:
        """
        새 핸드에 대한 공정성 증명 생성.

        Args:
            hand_id: 핸드 ID
            room_id: 방 ID
            client_seed: 클라이언트 시드 (None이면 자동 생성)
            nonce: 핸드 번호

        Returns:
            (HandFairnessProof, shuffled_deck)
        """
        # 서버 시드 생성
        server_seed, server_seed_hash = ProvablyFairEngine.generate_server_seed()

        # 클라이언트 시드 (제공되지 않으면 자동 생성)
        if client_seed is None:
            client_seed = ProvablyFairEngine.generate_client_seed()

        # 시드 조합 및 덱 셔플
        combined = ProvablyFairEngine.combine_seeds(server_seed, client_seed, nonce)
        deck = ProvablyFairEngine.shuffle_deck(combined)
        deck_hash = ProvablyFairEngine.deck_order_to_hash(deck)

        # 증명 객체 생성
        proof = HandFairnessProof(
            hand_id=hand_id,
            room_id=room_id,
            server_seed_hash=server_seed_hash,
            server_seed="",  # 핸드 종료 전까지 비공개
            client_seed=client_seed,
            nonce=nonce,
            deck_order_hash=deck_hash,
        )

        # 서버 시드는 별도로 저장 (핸드 종료 후 공개)
        proof.server_seed = server_seed  # 메모리에만 보관

        return proof, deck

    @staticmethod
    def reveal_proof(proof: HandFairnessProof, server_seed: str) -> HandFairnessProof:
        """
        핸드 종료 후 서버 시드 공개.

        Args:
            proof: 기존 증명 객체
            server_seed: 공개할 서버 시드

        Returns:
            공개된 증명 객체
        """
        proof.server_seed = server_seed
        proof.revealed_at = datetime.utcnow()
        return proof


class FairnessProofStore:
    """
    공정성 증명 저장소.

    핸드별로 증명 데이터를 저장하고 조회합니다.
    프로덕션에서는 Redis 또는 DB에 저장합니다.
    """

    def __init__(self):
        self._proofs: dict[str, HandFairnessProof] = {}
        self._server_seeds: dict[str, str] = {}  # hand_id -> server_seed (비공개)

    def store(self, proof: HandFairnessProof, server_seed: str) -> None:
        """증명 저장 (서버 시드는 별도 보관)."""
        self._proofs[proof.hand_id] = proof
        self._server_seeds[proof.hand_id] = server_seed

    def get_public(self, hand_id: str) -> HandFairnessProof | None:
        """공개 정보만 반환 (핸드 진행 중)."""
        proof = self._proofs.get(hand_id)
        if proof and not proof.is_revealed:
            # 서버 시드 없이 반환
            return HandFairnessProof(
                proof_id=proof.proof_id,
                hand_id=proof.hand_id,
                room_id=proof.room_id,
                server_seed_hash=proof.server_seed_hash,
                client_seed=proof.client_seed,
                nonce=proof.nonce,
                deck_order_hash=proof.deck_order_hash,
                created_at=proof.created_at,
            )
        return proof

    def reveal(self, hand_id: str) -> HandFairnessProof | None:
        """핸드 종료 후 서버 시드 공개."""
        proof = self._proofs.get(hand_id)
        server_seed = self._server_seeds.get(hand_id)

        if proof and server_seed:
            proof = ProvablyFairEngine.reveal_proof(proof, server_seed)
            self._proofs[hand_id] = proof
            return proof

        return None

    def get_revealed(self, hand_id: str) -> HandFairnessProof | None:
        """전체 정보 반환 (핸드 종료 후)."""
        return self._proofs.get(hand_id)


# 전역 저장소 인스턴스 (프로덕션에서는 Redis 기반으로 교체)
_proof_store: FairnessProofStore | None = None


def get_proof_store() -> FairnessProofStore:
    """공정성 증명 저장소 인스턴스 반환."""
    global _proof_store
    if _proof_store is None:
        _proof_store = FairnessProofStore()
    return _proof_store


def init_proof_store() -> FairnessProofStore:
    """공정성 증명 저장소 초기화."""
    global _proof_store
    _proof_store = FairnessProofStore()
    return _proof_store
