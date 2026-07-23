import { NextRequest, NextResponse } from "next/server";


export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname === "/login") {
    return NextResponse.next();
  }
  if (!request.cookies.has("llm_vulnhub_session")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}


export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
