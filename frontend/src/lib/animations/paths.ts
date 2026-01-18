/**
 * Animation Path Utilities
 * 경로 계산 유틸리티
 */

export interface Point {
  x: number;
  y: number;
}

// 기존 호환성 유지
export interface CurvedPathOptions {
  curvature?: number;
  direction?: 'up' | 'down' | 'auto';
}

/**
 * 두 점 사이의 직선 경로 (시작점, 끝점)
 */
export function calculateCurvedPath(
  start: Point,
  end: Point,
  _options: CurvedPathOptions = {}
): Point[] {
  return [start, end];
}

/**
 * 직선 SVG path
 */
export function calculateArcPath(
  start: Point,
  end: Point,
  _arcHeight: number = 50
): string {
  return `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
}

/**
 * 원형 경로 계산
 */
export function calculateCircularPath(
  center: Point,
  radius: number,
  startAngle: number,
  endAngle: number,
  steps: number = 20
): Point[] {
  const points: Point[] = [];
  const angleStep = (endAngle - startAngle) / steps;

  for (let i = 0; i <= steps; i++) {
    const angle = startAngle + angleStep * i;
    const radians = (angle * Math.PI) / 180;
    points.push({
      x: center.x + radius * Math.cos(radians),
      y: center.y + radius * Math.sin(radians),
    });
  }

  return points;
}

/**
 * 좌석 → 테이블 중앙 직선 경로
 */
export function createChipToTablePath(
  seatPosition: Point,
  tableCenter: Point,
  _curvature: number = 0.25
): Point[] {
  return [seatPosition, tableCenter];
}

/**
 * 테이블 중앙 → 승자 직선 경로
 */
export function createPotToWinnerPath(
  tableCenter: Point,
  winnerPosition: Point,
  _curvature: number = 0.2
): Point[] {
  return [tableCenter, winnerPosition];
}

/**
 * 여러 칩의 흩어진 위치 생성
 */
export function generateScatteredPositions(
  center: Point,
  count: number,
  radius: number = 30
): Point[] {
  const positions: Point[] = [];

  for (let i = 0; i < count; i++) {
    const angle = (i / count) * 2 * Math.PI + Math.random() * 0.5;
    const r = radius * (0.5 + Math.random() * 0.5);
    positions.push({
      x: center.x + r * Math.cos(angle),
      y: center.y + r * Math.sin(angle),
    });
  }

  return positions;
}

/**
 * Framer Motion keyframes 형식으로 경로 변환
 */
export function pathToKeyframes(points: Point[]): { x: number[]; y: number[] } {
  return {
    x: points.map(p => p.x),
    y: points.map(p => p.y),
  };
}
