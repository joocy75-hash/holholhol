/**
 * 칩 스택 이미지 생성 스크립트 v4
 *
 * 핵심 원칙:
 * - 칩 높이 제한: 각 스택당 최대 10칩 (총 최대 80칩)
 * - 금액 표현: 칩 개수가 아닌 색상 조합으로 표현
 *
 * 배치: 8스택 (최뒤3 + 뒤3 + 앞2)
 *    [최뒤좌][최뒤중][최뒤우]
 *       [뒤좌][뒤중][뒤우]
 *          [앞좌][앞우]
 *
 * 사용법: node scripts/generateChipStacks.js
 * 의존성: npm install sharp
 */

const sharp = require('sharp');
const fs = require('fs');
const path = require('path');

// 경로 설정
const CHIPS_DIR = path.join(__dirname, '../frontend/public/assets/chips');
const OUTPUT_DIR = path.join(CHIPS_DIR, 'stacks');

// 5색 칩 SVG 파일
const CHIP_SVGS = {
  red: path.join(CHIPS_DIR, 'chip_stack.svg'),
  green: path.join(CHIPS_DIR, 'greenchip.svg'),
  blue: path.join(CHIPS_DIR, 'bluechip.svg'),
  purple: path.join(CHIPS_DIR, 'purplechip.svg'),
  black: path.join(CHIPS_DIR, 'blackchip.svg'),
};

// 25단계 칩 스택 정의 (금액 범위는 chipStackMapping.ts에서 관리)
const CHIP_STACKS = [
  // 1-100 범위: 1:1 매핑 (10단계)
  { name: 'stack_01', count: 1, tier: 1 },
  { name: 'stack_02', count: 2, tier: 1 },
  { name: 'stack_03', count: 3, tier: 1 },
  { name: 'stack_04', count: 4, tier: 1 },
  { name: 'stack_05', count: 5, tier: 1 },
  { name: 'stack_06', count: 6, tier: 1 },
  { name: 'stack_07', count: 7, tier: 1 },
  { name: 'stack_08', count: 8, tier: 1 },
  { name: 'stack_09', count: 9, tier: 1 },
  { name: 'stack_10', count: 10, tier: 1 },
  // 100-500 범위: 점진적 증가 (7단계)
  { name: 'stack_12', count: 12, tier: 2 },
  { name: 'stack_16', count: 16, tier: 2 },
  { name: 'stack_20', count: 20, tier: 3 },
  { name: 'stack_25', count: 25, tier: 3 },
  { name: 'stack_30', count: 30, tier: 4 },
  { name: 'stack_36', count: 36, tier: 4 },
  { name: 'stack_42', count: 42, tier: 5 },
  // 500+ 범위: 높이 고정, 색상 변화 (8단계)
  { name: 'stack_48', count: 48, tier: 5 },
  { name: 'stack_54', count: 54, tier: 6 },
  { name: 'stack_60', count: 60, tier: 6 },
  { name: 'stack_64', count: 64, tier: 6 },
  { name: 'stack_68', count: 68, tier: 6 },
  { name: 'stack_72', count: 72, tier: 6 },
  { name: 'stack_76', count: 76, tier: 6 },
  { name: 'stack_max', count: 80, tier: 6 },
];

// 칩 크기 설정
const CHIP_WIDTH = 48;
const CHIP_HEIGHT = 28;
const CHIP_VERTICAL_OVERLAP = 21;
const STACK_HORIZONTAL_GAP = 2;
const ROW_VERTICAL_OFFSET = 14;
const CANVAS_PADDING = 2;

// 고정 캔버스 크기 (모든 이미지 동일 - 칩 스케일 통일)
// 8스택(3열) 기준: 너비 = 3*48 + 2*2 = 148, 높이 = 10칩높이 + 2행오프셋 + 패딩
const FIXED_CANVAS_WIDTH = 148;
const FIXED_CANVAS_HEIGHT = 121;

/**
 * 단일 칩 PNG 버퍼 생성
 */
async function getChipPNG(color) {
  const svgPath = CHIP_SVGS[color];
  return sharp(svgPath)
    .resize(CHIP_WIDTH, CHIP_HEIGHT)
    .png()
    .toBuffer();
}

/**
 * 칩 개수를 8개 스택으로 분배 (3줄: 최뒤3 + 뒤3 + 앞2)
 * 반환: [최뒤좌, 최뒤중, 최뒤우, 뒤좌, 뒤중, 뒤우, 앞좌, 앞우]
 */
function distributeChips(totalCount) {
  if (totalCount <= 2) {
    // 1스택: 앞좌만
    return [0, 0, 0, 0, 0, 0, totalCount, 0];
  } else if (totalCount <= 5) {
    // 2스택: 앞좌, 앞우
    const left = Math.ceil(totalCount / 2);
    const right = totalCount - left;
    return [0, 0, 0, 0, 0, 0, left, right];
  } else if (totalCount <= 15) {
    // 3스택: 뒤중, 앞좌, 앞우
    const backMid = Math.ceil(totalCount / 3);
    const remaining = totalCount - backMid;
    const frontLeft = Math.ceil(remaining / 2);
    const frontRight = remaining - frontLeft;
    return [0, 0, 0, 0, backMid, 0, frontLeft, frontRight];
  } else if (totalCount <= 30) {
    // 4스택: 뒤좌, 뒤우, 앞좌, 앞우 (뒷줄을 약간 높게)
    const backTotal = Math.ceil(totalCount * 0.55);
    const backLeft = Math.ceil(backTotal / 2);
    const backRight = backTotal - backLeft;
    const frontTotal = totalCount - backTotal;
    const frontLeft = Math.ceil(frontTotal / 2);
    const frontRight = frontTotal - frontLeft;
    return [0, 0, 0, backLeft, 0, backRight, frontLeft, frontRight];
  } else if (totalCount <= 50) {
    // 5스택: 뒤3개, 앞2개
    const backTotal = Math.ceil(totalCount * 0.55);
    const frontTotal = totalCount - backTotal;
    const backLeft = Math.ceil(backTotal / 3);
    const backMid = Math.ceil(backTotal / 3);
    const backRight = backTotal - backLeft - backMid;
    const frontLeft = Math.ceil(frontTotal / 2);
    const frontRight = frontTotal - frontLeft;
    return [0, 0, 0, backLeft, backMid, backRight, frontLeft, frontRight];
  } else {
    // 8스택: 최뒤3개, 뒤3개, 앞2개 (각 스택당 최대 10칩)
    const maxPerStack = 10;
    const stackCount = 8;
    const perStack = Math.min(maxPerStack, Math.ceil(totalCount / stackCount));

    // 균등 분배 후 나머지 조정
    let remaining = totalCount;
    const stacks = [];

    for (let i = 0; i < stackCount; i++) {
      const count = Math.min(perStack, remaining);
      stacks.push(count);
      remaining -= count;
    }

    // 앞줄부터 채우기 (시각적으로 더 나음)
    return [stacks[6], stacks[7], stacks[5], stacks[3], stacks[4], stacks[2], stacks[0], stacks[1]];
  }
}

/**
 * tier + 칩 개수 기반 색상 결정 (금액 표현)
 */
function getStackColors(tier, count) {
  // tier 1 (1-10칩): 칩 개수에 따라 색상 점진적 변화
  if (tier === 1) {
    if (count <= 3) {
      // 1-3칩: 빨강만
      return {
        farBackLeft: 'red', farBackMid: 'red', farBackRight: 'red',
        backLeft: 'red', backMid: 'red', backRight: 'red',
        frontLeft: 'red', frontRight: 'red'
      };
    } else if (count <= 6) {
      // 4-6칩: 뒤=초록, 앞=빨강
      return {
        farBackLeft: 'green', farBackMid: 'green', farBackRight: 'green',
        backLeft: 'green', backMid: 'green', backRight: 'green',
        frontLeft: 'red', frontRight: 'red'
      };
    } else {
      // 7-10칩: 뒤=파랑, 앞=초록
      return {
        farBackLeft: 'blue', farBackMid: 'blue', farBackRight: 'blue',
        backLeft: 'blue', backMid: 'blue', backRight: 'blue',
        frontLeft: 'green', frontRight: 'green'
      };
    }
  }

  switch (tier) {
    case 2: // 중소액 (100-170)
      return {
        farBackLeft: 'green', farBackMid: 'green', farBackRight: 'green',
        backLeft: 'green', backMid: 'green', backRight: 'green',
        frontLeft: 'red', frontRight: 'red'
      };
    case 3: // 중액 (170-280)
      return {
        farBackLeft: 'blue', farBackMid: 'blue', farBackRight: 'blue',
        backLeft: 'blue', backMid: 'blue', backRight: 'blue',
        frontLeft: 'green', frontRight: 'green'
      };
    case 4: // 중고액 (280-420)
      return {
        farBackLeft: 'purple', farBackMid: 'purple', farBackRight: 'purple',
        backLeft: 'purple', backMid: 'purple', backRight: 'purple',
        frontLeft: 'blue', frontRight: 'blue'
      };
    case 5: // 고액 (420-700)
      return {
        farBackLeft: 'black', farBackMid: 'black', farBackRight: 'black',
        backLeft: 'black', backMid: 'black', backRight: 'black',
        frontLeft: 'purple', frontRight: 'purple'
      };
    case 6: // 최고액 (700+) - 칩 개수에 따라 세분화
    default:
      if (count <= 54) {
        // 54칩: 최뒤=검정, 뒤=보라, 앞=보라
        return {
          farBackLeft: 'black', farBackMid: 'black', farBackRight: 'black',
          backLeft: 'purple', backMid: 'purple', backRight: 'purple',
          frontLeft: 'purple', frontRight: 'purple'
        };
      } else if (count <= 64) {
        // 60-64칩: 최뒤=검정, 뒤=검정, 앞=보라
        return {
          farBackLeft: 'black', farBackMid: 'black', farBackRight: 'black',
          backLeft: 'black', backMid: 'black', backRight: 'black',
          frontLeft: 'purple', frontRight: 'purple'
        };
      } else if (count <= 72) {
        // 68-72칩: 최뒤=검정, 뒤=검정, 앞=검정+보라
        return {
          farBackLeft: 'black', farBackMid: 'black', farBackRight: 'black',
          backLeft: 'black', backMid: 'black', backRight: 'black',
          frontLeft: 'black', frontRight: 'purple'
        };
      } else {
        // 76-max칩: 전체 검정
        return {
          farBackLeft: 'black', farBackMid: 'black', farBackRight: 'black',
          backLeft: 'black', backMid: 'black', backRight: 'black',
          frontLeft: 'black', frontRight: 'black'
        };
      }
  }
}

/**
 * 단일 스택의 칩들 생성
 */
function createStackComposites(chipCount, baseX, baseY, chipBuffers, stackColor) {
  const composites = [];
  for (let i = 0; i < chipCount; i++) {
    const y = baseY - i * (CHIP_HEIGHT - CHIP_VERTICAL_OVERLAP);
    composites.push({
      input: chipBuffers[stackColor],
      top: Math.round(y),
      left: Math.round(baseX),
    });
  }
  return composites;
}

/**
 * 칩 스택 이미지 생성
 */
async function generateChipStack(name, totalCount, tier, chipBuffers) {
  const [farBackLeftCount, farBackMidCount, farBackRightCount,
         backLeftCount, backMidCount, backRightCount,
         frontLeftCount, frontRightCount] = distributeChips(totalCount);
  const stackColors = getStackColors(tier, totalCount);

  const hasFarBackRow = farBackLeftCount > 0 || farBackMidCount > 0 || farBackRightCount > 0;
  const hasBackRow = backLeftCount > 0 || backMidCount > 0 || backRightCount > 0;

  // 각 스택의 높이 계산
  const calcHeight = (count) => count > 0 ? CHIP_HEIGHT + (count - 1) * (CHIP_HEIGHT - CHIP_VERTICAL_OVERLAP) : 0;
  const farBackLeftHeight = calcHeight(farBackLeftCount);
  const farBackMidHeight = calcHeight(farBackMidCount);
  const farBackRightHeight = calcHeight(farBackRightCount);
  const backLeftHeight = calcHeight(backLeftCount);
  const backMidHeight = calcHeight(backMidCount);
  const backRightHeight = calcHeight(backRightCount);
  const frontLeftHeight = calcHeight(frontLeftCount);
  const frontRightHeight = calcHeight(frontRightCount);

  const maxFarBackHeight = Math.max(farBackLeftHeight, farBackMidHeight, farBackRightHeight);
  const maxBackHeight = Math.max(backLeftHeight, backMidHeight, backRightHeight);
  const maxFrontHeight = Math.max(frontLeftHeight, frontRightHeight);
  const maxHeight = Math.max(maxFarBackHeight, maxBackHeight, maxFrontHeight);

  // 스택 개수 계산 (로깅용)
  const farBackStackCount = [farBackLeftCount, farBackMidCount, farBackRightCount].filter(c => c > 0).length;
  const backStackCount = [backLeftCount, backMidCount, backRightCount].filter(c => c > 0).length;
  const frontStackCount = [frontLeftCount, frontRightCount].filter(c => c > 0).length;

  // 고정 캔버스 크기 사용 (모든 이미지 동일 스케일)
  const canvasWidth = FIXED_CANVAS_WIDTH;
  const canvasHeight = FIXED_CANVAS_HEIGHT;

  // 실제 콘텐츠 크기 계산 (중앙 배치용)
  const farBackWidth = farBackStackCount * CHIP_WIDTH + Math.max(0, farBackStackCount - 1) * STACK_HORIZONTAL_GAP;
  const backWidth = backStackCount * CHIP_WIDTH + Math.max(0, backStackCount - 1) * STACK_HORIZONTAL_GAP;
  const frontWidth = frontStackCount * CHIP_WIDTH + (frontStackCount > 1 ? STACK_HORIZONTAL_GAP : 0);
  const contentWidth = Math.max(farBackWidth, backWidth, frontWidth, CHIP_WIDTH);

  let verticalOffset = 0;
  if (hasFarBackRow) verticalOffset = ROW_VERTICAL_OFFSET * 2;
  else if (hasBackRow) verticalOffset = ROW_VERTICAL_OFFSET;

  const contentHeight = maxHeight + verticalOffset + CANVAS_PADDING;

  // 중앙 배치를 위한 오프셋 (하단 중앙)
  const xOffset = (canvasWidth - contentWidth) / 2;
  const yOffset = canvasHeight - contentHeight;

  const composites = [];

  // 최뒤 스택들 (가장 먼저 그림)
  if (hasFarBackRow) {
    let currentX = xOffset + (contentWidth - farBackWidth) / 2;
    const rowBaseY = yOffset + contentHeight - maxFarBackHeight - ROW_VERTICAL_OFFSET * 2 - CANVAS_PADDING;

    if (farBackLeftCount > 0) {
      const baseY = rowBaseY + farBackLeftHeight - CHIP_HEIGHT;
      composites.push(...createStackComposites(farBackLeftCount, currentX, baseY, chipBuffers, stackColors.farBackLeft));
      currentX += CHIP_WIDTH + STACK_HORIZONTAL_GAP;
    }
    if (farBackMidCount > 0) {
      const baseY = rowBaseY + farBackMidHeight - CHIP_HEIGHT;
      composites.push(...createStackComposites(farBackMidCount, currentX, baseY, chipBuffers, stackColors.farBackMid));
      currentX += CHIP_WIDTH + STACK_HORIZONTAL_GAP;
    }
    if (farBackRightCount > 0) {
      const baseY = rowBaseY + farBackRightHeight - CHIP_HEIGHT;
      composites.push(...createStackComposites(farBackRightCount, currentX, baseY, chipBuffers, stackColors.farBackRight));
    }
  }

  // 뒤 스택들
  if (hasBackRow) {
    let currentX = xOffset + (contentWidth - backWidth) / 2;
    const rowBaseY = yOffset + contentHeight - maxBackHeight - (hasBackRow ? ROW_VERTICAL_OFFSET : 0) - CANVAS_PADDING;

    if (backLeftCount > 0) {
      const baseY = rowBaseY + backLeftHeight - CHIP_HEIGHT;
      composites.push(...createStackComposites(backLeftCount, currentX, baseY, chipBuffers, stackColors.backLeft));
      currentX += CHIP_WIDTH + STACK_HORIZONTAL_GAP;
    }
    if (backMidCount > 0) {
      const baseY = rowBaseY + backMidHeight - CHIP_HEIGHT;
      composites.push(...createStackComposites(backMidCount, currentX, baseY, chipBuffers, stackColors.backMid));
      currentX += CHIP_WIDTH + STACK_HORIZONTAL_GAP;
    }
    if (backRightCount > 0) {
      const baseY = rowBaseY + backRightHeight - CHIP_HEIGHT;
      composites.push(...createStackComposites(backRightCount, currentX, baseY, chipBuffers, stackColors.backRight));
    }
  }

  // 앞 스택들 (가장 마지막에 그림)
  {
    let currentX = xOffset + (contentWidth - frontWidth) / 2;
    const rowBaseY = yOffset + contentHeight - maxFrontHeight - CANVAS_PADDING;

    if (frontLeftCount > 0) {
      const baseY = rowBaseY + frontLeftHeight - CHIP_HEIGHT;
      composites.push(...createStackComposites(frontLeftCount, currentX, baseY, chipBuffers, stackColors.frontLeft));
      currentX += CHIP_WIDTH + STACK_HORIZONTAL_GAP;
    }
    if (frontRightCount > 0) {
      const baseY = rowBaseY + frontRightHeight - CHIP_HEIGHT;
      composites.push(...createStackComposites(frontRightCount, currentX, baseY, chipBuffers, stackColors.frontRight));
    }
  }

  // PNG 생성
  const outputPath = path.join(OUTPUT_DIR, `${name}.png`);
  await sharp({
    create: {
      width: Math.round(canvasWidth),
      height: Math.round(canvasHeight),
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    },
  })
    .composite(composites)
    .png({ compressionLevel: 9 })
    .toFile(outputPath);

  const stackCount = farBackStackCount + backStackCount + frontStackCount;
  console.log(`✓ ${name}.png (${totalCount}칩, ${stackCount}스택, tier${tier}, ${Math.round(canvasWidth)}x${Math.round(canvasHeight)}px)`);
}

/**
 * 메인 실행
 */
async function main() {
  console.log('🎰 칩 스택 이미지 생성 시작 (v4: 25단계, 최대 80칩)...\n');

  // 출력 디렉토리 확인
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  // SVG 파일 확인
  for (const [color, svgPath] of Object.entries(CHIP_SVGS)) {
    if (!fs.existsSync(svgPath)) {
      console.error(`❌ 칩 SVG 파일을 찾을 수 없습니다: ${svgPath}`);
      process.exit(1);
    }
    console.log(`✓ 발견: ${color} 칩 (${path.basename(svgPath)})`);
  }
  console.log('');

  // 칩 PNG 버퍼 생성
  console.log('📦 칩 PNG 변환 중...');
  const chipBuffers = {
    red: await getChipPNG('red'),
    green: await getChipPNG('green'),
    blue: await getChipPNG('blue'),
    purple: await getChipPNG('purple'),
    black: await getChipPNG('black'),
  };
  console.log('');

  // 모든 스택 생성
  console.log('🔨 스택 이미지 생성 중...');
  for (const stack of CHIP_STACKS) {
    await generateChipStack(stack.name, stack.count, stack.tier, chipBuffers);
  }

  console.log(`\n✅ 완료! ${CHIP_STACKS.length}개 이미지가 생성되었습니다.`);
  console.log(`📁 출력 위치: ${OUTPUT_DIR}`);
}

main().catch(console.error);
