// Single fixed demo tenant. Lives here (not in a component or route
// handler) so every server-side route handler attaches the same scope.
// The browser never sees or controls this value.
export const DEMO_TENANT_ID = "contextstore_demo";
