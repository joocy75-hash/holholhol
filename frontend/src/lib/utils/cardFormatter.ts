import type { Card, Suit, Rank } from '@/types/game';

// Suit display
export const SUIT_SYMBOLS: Record<Suit, string> = {
  c: '♣',
  d: '♦',
  h: '♥',
  s: '♠',
};

export const SUIT_NAMES: Record<Suit, string> = {
  c: 'Clubs',
  d: 'Diamonds',
  h: 'Hearts',
  s: 'Spades',
};

export const SUIT_COLORS: Record<Suit, 'red' | 'black'> = {
  c: 'black',
  d: 'red',
  h: 'red',
  s: 'black',
};

// Rank display
export const RANK_DISPLAY: Record<Rank, string> = {
  '2': '2',
  '3': '3',
  '4': '4',
  '5': '5',
  '6': '6',
  '7': '7',
  '8': '8',
  '9': '9',
  T: '10',
  J: 'J',
  Q: 'Q',
  K: 'K',
  A: 'A',
};

export const RANK_VALUES: Record<Rank, number> = {
  '2': 2,
  '3': 3,
  '4': 4,
  '5': 5,
  '6': 6,
  '7': 7,
  '8': 8,
  '9': 9,
  T: 10,
  J: 11,
  Q: 12,
  K: 13,
  A: 14,
};

// Format card for display
export function formatCard(card: Card): string {
  return `${SUIT_SYMBOLS[card.suit]}${RANK_DISPLAY[card.rank]}`;
}

// Format card for aria-label
export function formatCardAccessible(card: Card): string {
  return `${RANK_DISPLAY[card.rank]} of ${SUIT_NAMES[card.suit]}`;
}

// Parse card string (e.g., "As" -> { rank: 'A', suit: 's' })
export function parseCard(cardStr: string): Card | null {
  if (cardStr.length !== 2) return null;

  const rank = cardStr[0] as Rank;
  const suit = cardStr[1] as Suit;

  if (!RANK_DISPLAY[rank] || !SUIT_SYMBOLS[suit]) {
    return null;
  }

  return { rank, suit };
}

// Get card image path (for SVG cards)
export function getCardImagePath(card: Card): string {
  return `/cards/${card.rank}${card.suit}.svg`;
}

// Get card back image path
export function getCardBackPath(): string {
  return '/cards/back.svg';
}

// Compare cards for sorting
export function compareCards(a: Card, b: Card): number {
  const rankDiff = RANK_VALUES[b.rank] - RANK_VALUES[a.rank];
  if (rankDiff !== 0) return rankDiff;

  // Sort by suit: spades, hearts, diamonds, clubs
  const suitOrder: Record<Suit, number> = { s: 0, h: 1, d: 2, c: 3 };
  return suitOrder[a.suit] - suitOrder[b.suit];
}
