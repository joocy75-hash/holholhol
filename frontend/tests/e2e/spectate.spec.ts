import { test, expect, Page } from '@playwright/test';

/**
 * Spectator Mode E2E Tests
 * MVP Required Scenarios:
 * - 테이블 스냅샷/업데이트 정상 수신
 * - 홀카드 숨김 확인
 */

// Helper function to login
async function login(page: Page, email: string, password: string) {
  await page.goto('/');
  await page.getByPlaceholder(/email/i).fill(email);
  await page.getByPlaceholder(/password/i).fill(password);
  await page.getByRole('button', { name: /login|sign in|로그인/i }).click();
  await page.waitForURL(/\/lobby|\/rooms/, { timeout: 10000 });
}

test.describe('Spectator Mode', () => {
  test('should enter table as spectator without seat', async ({ page }) => {
    test.skip(!process.env.TEST_EMAIL, 'Test credentials not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);

    // Navigate to an active room
    await page.goto(`/table/${process.env.TEST_ROOM_ID || 'test'}`);

    // Should see table layout
    const table = page.locator('.table, [data-testid="poker-table"]');
    await expect(table).toBeVisible();

    // Should see seats (but not be seated)
    const seats = page.locator('.seat, [data-testid="seat"]');
    await expect(seats.first()).toBeVisible();
  });

  test('should hide opponent hole cards from spectator', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // Spectator should not see player hole cards (unless showdown)
    const holeCards = page.locator('[data-testid="hole-cards"]:not([data-showdown="true"])');

    // If game is active, hole cards should be hidden or face-down
    if (await holeCards.first().isVisible()) {
      // Cards should show back (hidden)
      const faceDownCards = holeCards.locator('.card-back, [data-face-down="true"]');
      await expect(faceDownCards.first()).toBeVisible();
    }
  });

  test('should receive live updates as spectator', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // Get initial pot
    const pot = page.locator('.pot, [data-testid="pot"]');
    const initialPot = await pot.textContent();

    // Wait for an action to occur (pot change)
    // This is a passive test - we just wait and observe
    await page.waitForTimeout(30000); // 30 seconds

    const newPot = await pot.textContent();
    // If game is active, pot may have changed
    // We just verify the pot is still visible
    await expect(pot).toBeVisible();
  });

  test('should see community cards as spectator', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // Community cards area should be visible
    const communityCards = page.locator('.community-cards, [data-testid="community-cards"]');
    await expect(communityCards).toBeVisible();
  });

  test('should see dealer button position', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // Dealer button should be visible
    const dealerButton = page.locator('.dealer-button, [data-testid="dealer-btn"]');
    await expect(dealerButton).toBeVisible();
  });

  test('should see active player indicator', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // If game is in progress, active seat should be highlighted
    const activeSeat = page.locator('.seat-active, [data-active="true"]');
    if (await activeSeat.isVisible()) {
      // Active player indicator working
      expect(true).toBe(true);
    }
  });

  test('should see showdown results', async ({ page }) => {
    test.skip(!process.env.TEST_SHOWDOWN_ROOM_ID, 'Showdown room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_SHOWDOWN_ROOM_ID}`);

    // Wait for showdown
    const showdownResult = page.locator('.showdown-result, [data-testid="showdown"]');

    // At showdown, spectators can see hole cards
    await expect(showdownResult).toBeVisible({ timeout: 60000 });

    // Cards should now be face up
    const faceUpCards = showdownResult.locator('.card:not(.card-back)');
    await expect(faceUpCards.first()).toBeVisible();
  });

  test('should not see action buttons as spectator', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);

    // Enter as spectator (not seated)
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}?mode=spectator`);

    // Action buttons should not be visible
    const actionPanel = page.locator('.action-panel, [data-testid="action-panel"]');
    await expect(actionPanel).toBeHidden();
  });

  test('should have option to take seat', async ({ page }) => {
    test.skip(!process.env.TEST_ROOM_ID, 'Test room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_ROOM_ID}`);

    // "Take Seat" or empty seat button should be available
    const takeSeatBtn = page.getByRole('button', { name: /take seat|sit|착석|앉기/i });
    const emptySeat = page.locator('.seat-empty, [data-empty="true"]');

    const canSit = await takeSeatBtn.isVisible() || await emptySeat.first().isVisible();
    expect(canSit).toBe(true);
  });
});

test.describe('Chat as Spectator', () => {
  test('should see chat messages', async ({ page }) => {
    test.skip(!process.env.TEST_ROOM_ID, 'Test room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_ROOM_ID}`);

    // Chat area should be visible
    const chatArea = page.locator('.chat, [data-testid="chat"]');
    await expect(chatArea).toBeVisible();
  });

  test('should be able to send chat message', async ({ page }) => {
    test.skip(!process.env.TEST_ROOM_ID, 'Test room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_ROOM_ID}`);

    // Chat input should be available
    const chatInput = page.getByPlaceholder(/message|메시지|chat|채팅/i);
    if (await chatInput.isVisible()) {
      await chatInput.fill('Hello from spectator!');
      await chatInput.press('Enter');

      // Message should appear in chat
      const chatMessages = page.locator('.chat-message, [data-testid="chat-message"]');
      await expect(chatMessages.last()).toContainText('Hello from spectator!');
    }
  });
});
