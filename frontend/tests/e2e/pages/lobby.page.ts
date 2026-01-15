/**
 * Lobby Page Object Model
 * 
 * Handles lobby UI interactions including table listing,
 * filtering, and navigation.
 * 
 * Updated to match actual frontend UI structure.
 * 
 * @requirements 2.1~2.5
 */

import { Page, Locator, expect } from '@playwright/test';

export class LobbyPage {
  readonly page: Page;
  
  // Locators - using actual CSS selectors
  readonly tableList: Locator;
  readonly tableCards: Locator;
  readonly continueButton: Locator;
  readonly logoutButton: Locator;
  readonly quickJoinButton: Locator;
  
  // Filter tabs
  readonly allTab: Locator;
  readonly holdemTab: Locator;
  readonly tournamentTab: Locator;
  
  // Loading indicator
  readonly loadingSpinner: Locator;

  constructor(page: Page) {
    this.page = page;
    
    // Table list elements - using actual selectors
    this.tableList = page.locator('main');
    this.tableCards = page.locator('[class*="holdem-card"], [class*="HoldemCard"]').or(
      page.locator('div').filter({ hasText: /참가하기/ }).locator('..')
    );
    this.continueButton = page.locator('button:has-text("계속하기")');
    this.logoutButton = page.locator('button:has-text("로그아웃")');
    this.quickJoinButton = page.locator('button:has-text("빠른 입장")');
    
    // Tab filters - GameTabs component
    this.allTab = page.locator('button:has-text("전체")');
    this.holdemTab = page.locator('button:has-text("홀덤")');
    this.tournamentTab = page.locator('button:has-text("토너먼트")');
    
    // Loading
    this.loadingSpinner = page.locator('.animate-spin');
  }

  /**
   * Navigate to lobby page
   */
  async goto(): Promise<void> {
    await this.page.goto('/lobby');
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Wait for tables to load
   * @requirements 2.1
   */
  async waitForTables(): Promise<void> {
    // Wait for loading to finish
    await this.page.waitForTimeout(1000);
    // Wait for either tables or empty state
    await this.page.waitForSelector('main', { state: 'visible' });
  }

  /**
   * Get count of displayed tables
   * @requirements 2.1
   */
  async getTableCount(): Promise<number> {
    // Look for table cards with "참가하기" button
    const joinButtons = this.page.locator('button:has-text("참가하기")');
    return await joinButtons.count();
  }

  /**
   * Join a specific table by navigating directly to the table URL
   * @requirements 2.2
   */
  async joinTable(tableId: string): Promise<void> {
    // Navigate directly to the table page
    // The lobby uses router.push() which doesn't create href links
    await this.page.goto(`/table/${tableId}`);
    await this.page.waitForURL(`**/table/${tableId}**`, { timeout: 10000 });
  }

  /**
   * Click on first available table to navigate
   * @requirements 2.2
   */
  async clickFirstTable(): Promise<void> {
    const joinButton = this.page.locator('button:has-text("참가하기")').first();
    await joinButton.click();
    await this.page.waitForURL('**/table/**');
  }

  /**
   * Click tab filter
   * @requirements 2.4
   */
  async clickTab(tab: 'all' | 'holdem' | 'tournament'): Promise<void> {
    switch (tab) {
      case 'all':
        await this.allTab.click();
        break;
      case 'holdem':
        await this.holdemTab.click();
        break;
      case 'tournament':
        await this.tournamentTab.click();
        break;
    }
    await this.page.waitForTimeout(500);
  }

  /**
   * Logout from the application
   * @requirements 2.5
   */
  async logout(): Promise<void> {
    await this.logoutButton.click();
    await this.page.waitForURL('**/login**');
  }

  /**
   * Check if continue banner is visible
   * @requirements 2.3
   */
  async hasContinueBanner(): Promise<boolean> {
    return await this.continueButton.isVisible();
  }

  /**
   * Click continue to return to active table
   * @requirements 2.3
   */
  async clickContinue(): Promise<void> {
    await this.continueButton.click();
    await this.page.waitForURL('**/table/**');
  }

  /**
   * Check if lobby is loaded
   */
  async isLoaded(): Promise<boolean> {
    // Check for main content area
    const mainVisible = await this.page.locator('main').isVisible();
    return mainVisible;
  }

  /**
   * Get active tab
   */
  async getActiveTab(): Promise<string> {
    // Check which tab has active styling
    const allActive = await this.allTab.evaluate(el => 
      el.classList.contains('active') || el.getAttribute('aria-selected') === 'true'
    );
    if (allActive) return 'all';
    
    const holdemActive = await this.holdemTab.evaluate(el => 
      el.classList.contains('active') || el.getAttribute('aria-selected') === 'true'
    );
    if (holdemActive) return 'holdem';
    
    return 'tournament';
  }

  /**
   * Check if user info is displayed
   */
  async hasUserInfo(): Promise<boolean> {
    // Look for user nickname or balance display
    const userInfo = this.page.locator('[class*="header"]').or(
      this.page.locator('header')
    );
    return await userInfo.isVisible();
  }
}
