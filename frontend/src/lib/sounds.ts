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

    // { once: true } 옵션으로 한 번만 실행 후 자동 제거 (메모리 누수 방지)
    this.audio.addEventListener('canplaythrough', () => {
      this.isReady = true;
    }, { once: true });

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

// =============================================================================
// 진동 피드백 매니저
// =============================================================================

type VibrationPattern = number | number[];

interface VibrationPresets {
  tap: VibrationPattern;       // 가벼운 탭
  action: VibrationPattern;    // 액션 수행
  win: VibrationPattern;       // 승리
  bigWin: VibrationPattern;    // 큰 승리
  turn: VibrationPattern;      // 내 차례
  error: VibrationPattern;     // 에러
  allIn: VibrationPattern;     // 올인
  fold: VibrationPattern;      // 폴드
}

class VibrationManager {
  private enabled = true;
  private intensity = 1.0; // 0.0 ~ 1.0

  // 진동 프리셋
  readonly presets: VibrationPresets = {
    tap: 10,                    // 10ms - 가벼운 탭
    action: 50,                 // 50ms - 일반 액션
    win: [100, 50, 100],       // 승리 패턴
    bigWin: [100, 50, 100, 50, 200],  // 큰 승리 패턴
    turn: [50, 100, 50],       // 내 차례 알림
    error: [100, 30, 100],     // 에러 패턴
    allIn: [50, 50, 100, 50, 150],    // 올인 패턴
    fold: 30,                   // 폴드 - 짧은 진동
  };

  /**
   * 진동 지원 여부 확인
   */
  isSupported(): boolean {
    return typeof navigator !== 'undefined' && 'vibrate' in navigator;
  }

  /**
   * 진동 활성화/비활성화
   */
  setEnabled(enabled: boolean) {
    this.enabled = enabled;
  }

  /**
   * 진동 강도 설정 (0.0 ~ 1.0)
   */
  setIntensity(intensity: number) {
    this.intensity = Math.max(0, Math.min(1, intensity));
  }

  /**
   * 진동 실행
   */
  vibrate(pattern: VibrationPattern) {
    if (!this.enabled || !this.isSupported()) return;

    // 강도 적용 (패턴의 진동 부분에만)
    const adjustedPattern = this.applyIntensity(pattern);

    try {
      navigator.vibrate(adjustedPattern);
    } catch {
      // 진동 실패 무시
    }
  }

  /**
   * 진동 중지
   */
  stop() {
    if (!this.isSupported()) return;
    try {
      navigator.vibrate(0);
    } catch {
      // 무시
    }
  }

  // 프리셋 진동 메서드
  tap() { this.vibrate(this.presets.tap); }
  action() { this.vibrate(this.presets.action); }
  win() { this.vibrate(this.presets.win); }
  bigWin() { this.vibrate(this.presets.bigWin); }
  turn() { this.vibrate(this.presets.turn); }
  error() { this.vibrate(this.presets.error); }
  allIn() { this.vibrate(this.presets.allIn); }
  fold() { this.vibrate(this.presets.fold); }

  /**
   * 액션 타입에 따른 진동
   */
  playForAction(action: string) {
    switch (action.toLowerCase()) {
      case 'fold':
        this.fold();
        break;
      case 'check':
        this.tap();
        break;
      case 'call':
        this.action();
        break;
      case 'bet':
      case 'raise':
        this.action();
        break;
      case 'all_in':
      case 'allin':
        this.allIn();
        break;
      default:
        this.tap();
    }
  }

  private applyIntensity(pattern: VibrationPattern): VibrationPattern {
    if (this.intensity >= 1.0) return pattern;

    if (typeof pattern === 'number') {
      return Math.round(pattern * this.intensity);
    }

    // 배열: 홀수 인덱스는 진동, 짝수 인덱스는 휴식
    return pattern.map((value, index) => 
      index % 2 === 0 ? Math.round(value * this.intensity) : value
    );
  }
}

export const vibrationManager = new VibrationManager();

// =============================================================================
// 통합 피드백 매니저
// =============================================================================

class FeedbackManager {
  private soundEnabled = true;
  private vibrationEnabled = true;

  /**
   * 사운드 활성화 설정
   */
  setSoundEnabled(enabled: boolean) {
    this.soundEnabled = enabled;
  }

  /**
   * 진동 활성화 설정
   */
  setVibrationEnabled(enabled: boolean) {
    this.vibrationEnabled = enabled;
    vibrationManager.setEnabled(enabled);
  }

  /**
   * 볼륨 설정
   */
  setVolume(volume: number) {
    soundManager.setVolume(volume);
    chipSoundManager.setVolume(volume);
  }

  /**
   * 진동 강도 설정
   */
  setVibrationIntensity(intensity: number) {
    vibrationManager.setIntensity(intensity);
  }

  /**
   * 액션 피드백 (사운드 + 진동)
   */
  playAction(action: string) {
    if (this.soundEnabled) {
      soundManager.play(action);
    }
    if (this.vibrationEnabled) {
      vibrationManager.playForAction(action);
    }
  }

  /**
   * 승리 피드백
   */
  playWin(isBigWin = false) {
    if (this.soundEnabled) {
      chipSoundManager.playWin();
    }
    if (this.vibrationEnabled) {
      if (isBigWin) {
        vibrationManager.bigWin();
      } else {
        vibrationManager.win();
      }
    }
  }

  /**
   * 내 차례 피드백
   */
  playTurn() {
    if (this.vibrationEnabled) {
      vibrationManager.turn();
    }
  }

  /**
   * 칩 사운드
   */
  playChip(type: 'call' | 'allin' | 'collect' | 'win') {
    if (this.soundEnabled) {
      chipSoundManager.play(type);
    }
  }

  /**
   * 에러 피드백
   */
  playError() {
    if (this.vibrationEnabled) {
      vibrationManager.error();
    }
  }
}

export const feedbackManager = new FeedbackManager();
