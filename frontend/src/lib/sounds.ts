// 오디오 스프라이트 기반 사운드 매니저
type SpriteKey = 'fold' | 'check' | 'call' | 'raise' | 'allin';

interface SpriteData {
  src: string[];
  sprite: Record<SpriteKey, [number, number]>;
}

const SPRITE_DATA: SpriteData = {
  src: ['/sounds/actions/actions_sprite.webm', '/sounds/actions/actions_sprite.m4a'],
  sprite: {
    fold: [0, 701],
    check: [701, 634],
    call: [1335, 701],
    raise: [2036, 767],
    allin: [2803, 1401],
  },
};

class SoundManager {
  private audio: HTMLAudioElement | null = null;
  private isReady = false;
  private volume = 0.5;

  init() {
    if (this.audio || typeof window === 'undefined') return;

    // WebM 지원 여부 확인
    const testAudio = document.createElement('audio');
    const canPlayWebm = testAudio.canPlayType('audio/webm; codecs=opus');
    const src = canPlayWebm ? SPRITE_DATA.src[0] : SPRITE_DATA.src[1];

    this.audio = new Audio(src);
    this.audio.volume = this.volume;
    this.audio.preload = 'auto';

    this.audio.addEventListener('canplaythrough', () => {
      this.isReady = true;
    });

    // 프리로드
    this.audio.load();
  }

  play(action: string | { type: string }) {
    if (!this.audio) this.init();
    if (!this.audio) return;

    // 액션 타입 추출 (객체 또는 문자열)
    const actionType = typeof action === 'string' ? action : action.type;
    if (!actionType) return;

    // 액션 타입 매핑
    let mappedAction = actionType.replace('_', '');
    // bet은 raise와 같은 사운드 사용 (둘 다 돈을 거는 행위)
    if (mappedAction === 'bet') mappedAction = 'raise';
    const key = mappedAction as SpriteKey;
    const sprite = SPRITE_DATA.sprite[key];

    if (!sprite) {
      console.warn(`Unknown action sound: ${actionType}`);
      return;
    }

    const [start, duration] = sprite;

    // 현재 재생 중지 후 새 위치에서 재생
    this.audio.currentTime = start / 1000;
    this.audio.play().catch(() => {
      // 자동재생 차단 - 무시
    });

    // duration 후 정지
    setTimeout(() => {
      if (this.audio) {
        this.audio.pause();
      }
    }, duration);
  }

  setVolume(vol: number) {
    this.volume = Math.max(0, Math.min(1, vol));
    if (this.audio) {
      this.audio.volume = this.volume;
    }
  }
}

export const soundManager = new SoundManager();

// 칩 사운드 타입
type ChipSoundKey = 'call' | 'allin' | 'collect' | 'win';

// 칩 사운드 매니저 (개별 파일 방식)
class ChipSoundManager {
  private audioPool: Map<ChipSoundKey, HTMLAudioElement[]> = new Map();
  private volume = 0.6;
  private poolSize = 5; // 동시 재생 지원 (최대 5개)

  private getSrc(key: ChipSoundKey): string {
    return `/sounds/chips/chip_${key}.webm`;
  }

  private getOrCreateAudio(key: ChipSoundKey): HTMLAudioElement | null {
    if (typeof window === 'undefined') return null;

    // 풀 초기화
    if (!this.audioPool.has(key)) {
      this.audioPool.set(key, []);
    }

    const pool = this.audioPool.get(key)!;

    // 사용 가능한 오디오 찾기
    for (const audio of pool) {
      if (audio.paused || audio.ended) {
        audio.currentTime = 0;
        return audio;
      }
    }

    // 풀에 여유 있으면 새로 생성
    if (pool.length < this.poolSize) {
      const audio = new Audio(this.getSrc(key));
      audio.volume = this.volume;
      audio.preload = 'auto';
      pool.push(audio);
      return audio;
    }

    // 풀 가득 차면 첫 번째 재사용
    const audio = pool[0];
    audio.currentTime = 0;
    return audio;
  }

  play(type: ChipSoundKey) {
    const audio = this.getOrCreateAudio(type);
    if (!audio) return;

    audio.play().catch(() => {
      // 자동재생 차단 - 무시
    });
  }

  // 편의 메서드
  playCall() { this.play('call'); }
  playAllin() { this.play('allin'); }
  playCollect() { this.play('collect'); }
  playWin() { this.play('win'); }

  setVolume(vol: number) {
    this.volume = Math.max(0, Math.min(1, vol));
    this.audioPool.forEach(pool => {
      pool.forEach(audio => {
        audio.volume = this.volume;
      });
    });
  }
}

export const chipSoundManager = new ChipSoundManager();
