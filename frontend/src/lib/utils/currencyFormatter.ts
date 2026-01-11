// Format currency for display
export function formatCurrency(amount: number, showSign = false): string {
  const formatted = new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'KRW',
    maximumFractionDigits: 0,
  }).format(amount);

  if (showSign && amount > 0) {
    return `+${formatted}`;
  }

  return formatted;
}

// Format chip amount (abbreviated)
export function formatChips(amount: number): string {
  if (amount >= 1_000_000) {
    return `${(amount / 1_000_000).toFixed(1)}M`;
  }
  if (amount >= 1_000) {
    return `${(amount / 1_000).toFixed(1)}K`;
  }
  return amount.toString();
}

// Format as dollar amount (for display in game)
export function formatDollars(amount: number, showSign = false): string {
  const formatted = `$${amount.toLocaleString()}`;

  if (showSign && amount > 0) {
    return `+${formatted}`;
  }

  return formatted;
}

// Format blinds (e.g., "10/20")
export function formatBlinds(small: number, big: number): string {
  return `${small}/${big}`;
}

// Parse blinds string (e.g., "10/20" -> { small: 10, big: 20 })
export function parseBlinds(blindsStr: string): { small: number; big: number } | null {
  const parts = blindsStr.split('/');
  if (parts.length !== 2) return null;

  const small = parseInt(parts[0], 10);
  const big = parseInt(parts[1], 10);

  if (isNaN(small) || isNaN(big)) return null;

  return { small, big };
}
