import { test, expect } from '@playwright/test';

/**
 * Authentication E2E Tests
 * Tests user registration and login flows
 */
test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display login form on auth page', async ({ page }) => {
    await expect(page.locator('form')).toBeVisible();
    await expect(page.getByPlaceholder(/email/i)).toBeVisible();
    await expect(page.getByPlaceholder(/password/i)).toBeVisible();
  });

  test('should show validation errors for empty form submission', async ({ page }) => {
    // Click login button without filling form
    await page.getByRole('button', { name: /login|sign in|로그인/i }).click();

    // Should show validation errors
    await expect(page.locator('.error, [role="alert"]')).toBeVisible();
  });

  test('should switch between login and register forms', async ({ page }) => {
    // Find and click register link/tab
    const registerLink = page.getByRole('link', { name: /register|sign up|회원가입/i });
    if (await registerLink.isVisible()) {
      await registerLink.click();
      // Should show nickname field (only in register form)
      await expect(page.getByPlaceholder(/nickname|닉네임/i)).toBeVisible();
    }
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.getByPlaceholder(/email/i).fill('invalid@test.com');
    await page.getByPlaceholder(/password/i).fill('wrongpassword123');
    await page.getByRole('button', { name: /login|sign in|로그인/i }).click();

    // Should show error message
    await expect(page.locator('.error, [role="alert"], .toast-error')).toBeVisible({
      timeout: 5000,
    });
  });

  test('should redirect to lobby after successful login', async ({ page }) => {
    // This test requires a valid test account
    // Skip if no test credentials available
    test.skip(!process.env.TEST_EMAIL || !process.env.TEST_PASSWORD,
      'Test credentials not configured');

    await page.getByPlaceholder(/email/i).fill(process.env.TEST_EMAIL!);
    await page.getByPlaceholder(/password/i).fill(process.env.TEST_PASSWORD!);
    await page.getByRole('button', { name: /login|sign in|로그인/i }).click();

    // Should redirect to lobby
    await expect(page).toHaveURL(/\/lobby|\/rooms/);
  });
});
