/**
 * 칩 스택 이미지 매핑 (v4)
 *
 * 금액에 따라 미리 생성된 칩 스택 이미지를 반환합니다.
 * 25단계의 이미지가 있으며, 금액 범위에 따라 적절한 이미지가 선택됩니다.
 *
 * 설계 원칙:
 * - 칩 높이 제한: 각 스택당 최대 10칩 (총 최대 80칩)
 * - 금액 표현: 칩 개수가 아닌 색상 조합으로 표현
 * - 1-100 범위: 1:1 매핑 (10단계)
 * - 100-500 범위: 점진적 증가 (7단계)
 * - 500+ 범위: 높이 고정, 색상 변화 (8단계)
 */

// 금액 범위 → 이미지 매핑 테이블
export const CHIP_STACK_THRESHOLDS = [
  // 1-100 범위: 1:1 매핑 (10단계)
  { min: 0, max: 10, image: 'stack_01.png' },       // 1-10: 1칩
  { min: 11, max: 20, image: 'stack_02.png' },      // 11-20: 2칩
  { min: 21, max: 30, image: 'stack_03.png' },      // 21-30: 3칩
  { min: 31, max: 40, image: 'stack_04.png' },      // 31-40: 4칩
  { min: 41, max: 50, image: 'stack_05.png' },      // 41-50: 5칩
  { min: 51, max: 60, image: 'stack_06.png' },      // 51-60: 6칩
  { min: 61, max: 70, image: 'stack_07.png' },      // 61-70: 7칩
  { min: 71, max: 80, image: 'stack_08.png' },      // 71-80: 8칩
  { min: 81, max: 90, image: 'stack_09.png' },      // 81-90: 9칩
  { min: 91, max: 100, image: 'stack_10.png' },     // 91-100: 10칩

  // 100-500 범위: 점진적 증가 (7단계)
  { min: 101, max: 130, image: 'stack_12.png' },    // 101-130: 12칩
  { min: 131, max: 170, image: 'stack_16.png' },    // 131-170: 16칩
  { min: 171, max: 220, image: 'stack_20.png' },    // 171-220: 20칩
  { min: 221, max: 280, image: 'stack_25.png' },    // 221-280: 25칩
  { min: 281, max: 350, image: 'stack_30.png' },    // 281-350: 30칩
  { min: 351, max: 420, image: 'stack_36.png' },    // 351-420: 36칩
  { min: 421, max: 500, image: 'stack_42.png' },    // 421-500: 42칩

  // 500+ 범위: 높이 고정, 색상 변화 (8단계)
  { min: 501, max: 700, image: 'stack_48.png' },    // 501-700: 48칩
  { min: 701, max: 1000, image: 'stack_54.png' },   // 701-1000: 54칩
  { min: 1001, max: 1500, image: 'stack_60.png' },  // 1001-1500: 60칩
  { min: 1501, max: 2500, image: 'stack_64.png' },  // 1501-2500: 64칩
  { min: 2501, max: 4000, image: 'stack_68.png' },  // 2501-4000: 68칩
  { min: 4001, max: 7000, image: 'stack_72.png' },  // 4001-7000: 72칩
  { min: 7001, max: 15000, image: 'stack_76.png' }, // 7001-15000: 76칩
  { min: 15001, max: Infinity, image: 'stack_max.png' }, // 15001+: 80칩 (최대)
] as const;

// 이미지 경로 기본값
const CHIP_STACKS_BASE_PATH = '/assets/chips/stacks';

/**
 * 금액에 해당하는 칩 스택 이미지 경로 반환
 * O(1) 룩업 (12개 이하의 비교)
 */
export function getChipStackImage(amount: number): string {
  // 빈 금액 처리
  if (amount <= 0) {
    return `${CHIP_STACKS_BASE_PATH}/stack_01.png`;
  }

  // 테이블에서 해당 범위 찾기
  const threshold = CHIP_STACK_THRESHOLDS.find(
    (t) => amount >= t.min && amount <= t.max
  );

  return `${CHIP_STACKS_BASE_PATH}/${threshold?.image ?? 'stack_01.png'}`;
}

/**
 * 모든 칩 스택 이미지 경로 목록 (프리로딩용)
 */
export function getAllChipStackImages(): string[] {
  return CHIP_STACK_THRESHOLDS.map(
    (t) => `${CHIP_STACKS_BASE_PATH}/${t.image}`
  );
}

// 프리로딩 상태 추적
let preloadPromise: Promise<void> | null = null;

/**
 * 모든 칩 스택 이미지를 미리 로드
 * 한 번만 실행되며, 중복 호출 시 기존 Promise 반환
 */
export function preloadChipStackImages(): Promise<void> {
  if (preloadPromise) {
    return preloadPromise;
  }

  const images = getAllChipStackImages();

  preloadPromise = Promise.all(
    images.map(
      (src) =>
        new Promise<void>((resolve) => {
          const img = new Image();
          img.onload = () => resolve();
          img.onerror = () => resolve(); // 에러 시에도 계속 진행
          img.src = src;
        })
    )
  ).then(() => {
    // 완료 시 아무것도 반환하지 않음
  });

  return preloadPromise;
}
