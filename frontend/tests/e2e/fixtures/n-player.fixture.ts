/**
 * N-Player Fixtures for E2E Tests
 * 
 * Provides support for 2-6 simultaneous players
 * for testing complex scenarios like side pots.
 */

/* eslint-disable react-hooks/rules-of-hooks */

import { test as base, Page, BrowserContext, Browser } from '@playwright/test';
import { LoginPage } from '../pages/login.page.js';
import { LobbyPage } from '../pages/lobby.page.js';
import { TablePage } from '../pages/table.page.js';
import { createTestUsers, TestUser } from '../utils/test-users.js';
import { cheatAPI } from '../utils/cheat-api.js';

/**
 * Player session with all necessary page objects
 */
export interface PlayerSession {
  page: Page;
  context: BrowserContext;
  user: TestUser;
  tablePage: TablePage;
  lobbyPage: LobbyPage;
  position: number;
}

/**
 * N-player fixture interface
 */
export interface NPlayerFixtures {
  /** Test table ID (auto-created and cleaned up) */
  tableId: string;
  /** Create N player sessions (2-6) */
  createPlayers: (count: number) => Promise<PlayerSession[]>;
  /** Setup all players at a table with specified buy-ins */
  setupPlayersAtTable: (
    players: PlayerSession[],
    tableId: string,
    buyIns: number[]
  ) => Promise<void>;
  /** Cleanup all player sessions */
  cleanupPlayers: (players: PlayerSession[]) => Promise<void>;
}

/**
 * Create an authenticated player session
 */
async function createPlayerSession(
  browser: Browser,
  user: TestUser,
  position: number
): Promise<PlayerSession> {
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // Login
  const loginPage = new LoginPage(page);
  await loginPage.goto();
  await loginPage.login(user.email, user.password);
  await page.waitForURL('**/lobby**', { timeout: 10000 });
  
  return {
    page,
    context,
    user,
    tablePage: new TablePage(page),
    lobbyPage: new LobbyPage(page),
    position,
  };
}

/**
 * Extended test with N-player support
 */
export const test = base.extend<NPlayerFixtures>({
  tableId: async ({}, use) => {
    // Create a test table for each test
    const tableId = await cheatAPI.createTestTable({
      name: `N-Player Test Table ${Date.now()}`,
      smallBlind: 10,
      bigBlind: 20,
    });
    
    await use(tableId);
    
    // Cleanup after test
    try {
      await cheatAPI.deleteTable(tableId);
    } catch {
      // Ignore cleanup errors
    }
  },

  createPlayers: async ({ browser }, use) => {
    const activeSessions: PlayerSession[] = [];
    
    const create = async (count: number): Promise<PlayerSession[]> => {
      if (count < 2 || count > 6) {
        throw new Error('Player count must be between 2 and 6');
      }
      
      const users = await createTestUsers(count);
      const sessions: PlayerSession[] = [];
      
      for (let i = 0; i < count; i++) {
        const session = await createPlayerSession(browser, users[i], i);
        sessions.push(session);
        activeSessions.push(session);
      }
      
      return sessions;
    };
    
    await use(create);
    
    // Cleanup all sessions
    for (const session of activeSessions) {
      await session.context.close();
    }
  },

  setupPlayersAtTable: async ({}, use) => {
    const setup = async (
      players: PlayerSession[],
      tableId: string,
      buyIns: number[]
    ) => {
      if (players.length !== buyIns.length) {
        throw new Error('Buy-in array must match player count');
      }
      
      // Each player joins and sits at the table
      for (let i = 0; i < players.length; i++) {
        const player = players[i];
        const buyIn = buyIns[i];
        
        await player.lobbyPage.joinTable(tableId);
        await player.tablePage.waitForTableLoad();
        await player.tablePage.clickEmptySeat(i);
        await player.tablePage.confirmBuyIn(buyIn);
        
        // Small delay between players joining
        await player.page.waitForTimeout(300);
      }
      
      // Wait for all players to be seated
      await players[0].page.waitForTimeout(500);
    };
    
    await use(setup);
  },

  cleanupPlayers: async ({}, use) => {
    const cleanup = async (players: PlayerSession[]) => {
      for (const player of players) {
        try {
          await player.tablePage.leaveTable();
        } catch {
          // Ignore errors during cleanup
        }
      }
    };
    
    await use(cleanup);
  },
});

export { expect } from '@playwright/test';
