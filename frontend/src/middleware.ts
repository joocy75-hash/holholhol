import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Middleware to protect test pages in production environment.
 * Blocks access to development/testing pages when NODE_ENV is production.
 */
export function middleware(request: NextRequest) {
  // Only block in production environment
  if (process.env.NODE_ENV === 'production') {
    const pathname = request.nextUrl.pathname

    // List of test pages to block in production
    const blockedPaths = ['/bot-test', '/chip-test']

    // Check if the request is for a blocked path
    if (blockedPaths.some((path) => pathname.startsWith(path))) {
      // Redirect to home page
      return NextResponse.redirect(new URL('/', request.url))
    }
  }

  return NextResponse.next()
}

// Configure which paths the middleware runs on
export const config = {
  matcher: ['/bot-test/:path*', '/chip-test/:path*'],
}
