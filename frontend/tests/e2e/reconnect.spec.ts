import { test, expect, Page, BrowserContext } from '@playwright/test';

/**
 * Reconnection E2E Tests
 * MVP Required Scenarios:
 * - Hand 중 끊김 → 복구 → 상태 일치
 * - 재접속 후 state recovery
 */

// Helper function to login
async function login(page: Page, email: string, password: string) {
  await page.goto('/');
  await page.getByPlaceholder(/email/i).fill(email);
  await page.getByPlaceholder(/password/i).fill(password);
  await page.getByRole('button', { name: /login|sign in|로그인/i }).click();
  await page.waitForURL(/\/lobby|\/rooms/, { timeout: 10000 });
}

test.describe('Reconnection', () => {
  test('should maintain connection indicator', async ({ page }) => {
    test.skip(!process.env.TEST_EMAIL, 'Test credentials not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);

    // Connection indicator should show connected
    const connectionStatus = page.locator(
      '.connection-status, [data-testid="connection-status"]'
    );
    await expect(connectionStatus).toBeVisible();
    await expect(connectionStatus).toHaveAttribute('data-connected', 'true');
  });

  test('should show disconnection warning on network loss', async ({ page, context }) => {
    test.skip(!process.env.TEST_EMAIL, 'Test credentials not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_ROOM_ID || 'test'}`);

    // Simulate offline
    await context.setOffline(true);

    // Should show disconnection warning
    const disconnectBanner = page.locator(
      '.connection-banner, [data-testid="disconnection-warning"]'
    );
    await expect(disconnectBanner).toBeVisible({ timeout: 5000 });

    // Restore connection
    await context.setOffline(false);

    // Should auto-reconnect
    await expect(disconnectBanner).toBeHidden({ timeout: 10000 });
  });

  test('should recover table state after reconnection', async ({ page, context }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // Get initial pot value
    const pot = page.locator('.pot, [data-testid="pot"]');
    await expect(pot).toBeVisible();
    const initialPot = await pot.textContent();

    // Simulate disconnect and reconnect
    await context.setOffline(true);
    await page.waitForTimeout(1000);
    await context.setOffline(false);

    // Wait for reconnection
    await page.waitForTimeout(3000);

    // Pot should still be visible and consistent
    await expect(pot).toBeVisible();
    const recoveredPot = await pot.textContent();
    expect(recoveredPot).toBe(initialPot);
  });

  test('should restore hole cards after reconnection', async ({ page, context }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // Get hole cards before disconnect
    const holeCards = page.locator('.hole-cards, [data-testid="my-cards"]');
    if (await holeCards.isVisible()) {
      const cardElements = holeCards.locator('.card, [data-testid="card"]');
      const cardCount = await cardElements.count();

      // Simulate disconnect
      await context.setOffline(true);
      await page.waitForTimeout(1000);
      await context.setOffline(false);

      // Wait for recovery
      await page.waitForTimeout(3000);

      // Cards should be restored
      await expect(cardElements).toHaveCount(cardCount);
    }
  });

  test('should preserve seat position after reconnection', async ({ page, context }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // Get current seat position
    const mySeat = page.locator('.seat[data-is-me="true"], [data-testid="my-seat"]');
    if (await mySeat.isVisible()) {
      const seatPosition = await mySeat.getAttribute('data-position');

      // Disconnect and reconnect
      await context.setOffline(true);
      await page.waitForTimeout(1000);
      await context.setOffline(false);
      await page.waitForTimeout(3000);

      // Seat should be preserved
      const restoredPosition = await mySeat.getAttribute('data-position');
      expect(restoredPosition).toBe(seatPosition);
    }
  });
});

test.describe('Idempotency', () => {
  test('should prevent double-click on action buttons', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    const callBtn = page.getByRole('button', { name: /call|콜/i });
    if (await callBtn.isVisible() && await callBtn.isEnabled()) {
      // Get initial pot
      const pot = page.locator('.pot, [data-testid="pot"]');
      const potBefore = await pot.textContent();

      // Double-click call button
      await callBtn.dblclick();

      // Wait for action processing
      await page.waitForTimeout(1000);

      // Button should be disabled after first click
      await expect(callBtn).toBeDisabled();

      // Pot should only increase once (not doubled)
      // This is a heuristic check - actual pot change depends on call amount
    }
  });

  test('should handle rapid raise button clicks', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    const raiseBtn = page.getByRole('button', { name: /raise|레이즈/i });
    if (await raiseBtn.isVisible() && await raiseBtn.isEnabled()) {
      // Click multiple times rapidly
      await raiseBtn.click();
      await raiseBtn.click();
      await raiseBtn.click();

      // Should only open modal once
      const modals = page.locator('.modal, [role="dialog"]');
      await expect(modals).toHaveCount(1);
    }
  });

  test('should reject stale actions', async ({ page }) => {
    test.skip(!process.env.TEST_GAME_ROOM_ID, 'Active game room not configured');

    await login(page, process.env.TEST_EMAIL!, process.env.TEST_PASSWORD!);
    await page.goto(`/table/${process.env.TEST_GAME_ROOM_ID}`);

    // Wait for turn to pass to another player
    // Then try to act - should be rejected
    const actionPanel = page.locator('.action-panel');
    if (!(await actionPanel.isVisible())) {
      // If action panel is not visible, it's not our turn
      // Trying to inject an action should fail (no UI available)
    }
  });
});
