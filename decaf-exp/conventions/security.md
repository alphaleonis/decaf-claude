# Security Conventions

Language-agnostic security patterns for code review. These issues fall under RULE 0
(unrecoverable production risks) and use MUST severity.

## Security Categories

### SECURITY_INJECTION

Untrusted input incorporated into commands, queries, or expressions without proper
sanitization or parameterization.

**Patterns to flag:**
- String concatenation in SQL/database queries
- User input in shell/OS commands
- User input in LDAP queries
- User input in XML/XPath expressions
- Dynamic code evaluation with user input (eval, reflection with user strings)

**What to look for:**
```
# Any language - string interpolation in queries
query = "SELECT * FROM users WHERE id = " + userId
query = $"SELECT * FROM users WHERE id = {userId}"
query = f"SELECT * FROM users WHERE id = {user_id}"

# Command execution with user input
Process.Start("cmd", "/c " + userInput)
exec("ping " + hostname)
os.system(f"convert {filename}")
```

**Correct patterns:**
- Parameterized queries / prepared statements
- ORM methods with parameter binding
- Allowlist validation before any dynamic execution
- Escape functions specific to the target context

---

### SECURITY_AUTH_BYPASS

Missing or insufficient authentication/authorization checks that allow unauthorized
access to resources or operations.

**Patterns to flag:**
- Endpoints without authentication middleware
- Authorization checks missing after authentication
- Client-side only authorization (server trusts client claims)
- Predictable/enumerable resource identifiers without ownership check
- Role checks that can be bypassed

**What to look for:**
```
# Missing authorization - user can access any record by ID
public async Task<User> GetUser(int id) {
    return await db.Users.FindAsync(id);  // No ownership check
}

# Client-controlled authorization
if (request.Headers["X-Is-Admin"] == "true") { /* grant access */ }

# Missing authentication on sensitive endpoint
[HttpPost("api/admin/delete-user")]  // No [Authorize] attribute
public async Task DeleteUser(int id) { ... }
```

**Correct patterns:**
- Verify current user owns or has permission to access the resource
- Server-side role/permission checks from authenticated session
- Defense in depth (multiple authorization layers)

---

### SECURITY_SECRETS_EXPOSED

Hardcoded credentials, API keys, tokens, or other secrets in source code,
configuration files committed to version control, or logged output.

**Patterns to flag:**
- Hardcoded passwords, API keys, connection strings with credentials
- Secrets in appsettings.json/config files without environment variable substitution
- Private keys or certificates in source
- Secrets written to logs
- Secrets in error messages returned to users

**What to look for:**
```
# Hardcoded secrets
var apiKey = "sk-proj-abc123..."
connectionString = "Server=...;Password=hunter2;..."
private_key = "-----BEGIN RSA PRIVATE KEY-----"

# Secrets in logs
logger.Info($"Connecting with password: {password}")
Console.WriteLine($"API response: {apiKeyFromConfig}")
```

**Correct patterns:**
- Environment variables or secure secret stores (Azure Key Vault, AWS Secrets Manager)
- Configuration providers that read from secure sources
- Sanitized logging that masks sensitive values

---

### SECURITY_SSRF

Server-Side Request Forgery - application fetches URLs provided or influenced by
user input without validation, allowing access to internal resources.

**Patterns to flag:**
- HTTP client requests to user-provided URLs without validation
- URL construction from user input without allowlist
- Redirect following that could reach internal hosts
- Image/file fetching from user URLs

**What to look for:**
```
# Unvalidated URL fetch
var response = await httpClient.GetAsync(userProvidedUrl);
WebRequest.Create(urlFromInput).GetResponse();
requests.get(user_url)

# Partial validation insufficient
if (url.StartsWith("https://")) { fetch(url); }  // Can still reach internal HTTPS services
```

**Correct patterns:**
- Allowlist of permitted domains/hosts
- Validate URL resolves to expected IP ranges (not internal/private)
- Disable redirect following or validate redirect targets
- Use dedicated service accounts with network restrictions

---

### SECURITY_RACE_CONDITION

Time-of-check to time-of-use (TOCTOU) vulnerabilities where state can change
between validation and action, especially in financial or resource operations.

**Patterns to flag:**
- Balance/inventory check followed by separate deduction without locking
- Permission check followed by action without atomic guarantee
- File existence check followed by file operation
- Double-spend vulnerabilities in financial operations

**What to look for:**
```
# Race condition - check and modify are separate operations
var balance = await GetBalance(userId);
if (balance >= amount) {
    await Withdraw(userId, amount);  // Another request could withdraw between check and here
}

# File TOCTOU
if (File.Exists(path)) {
    File.Delete(path);  // File could be replaced between check and delete
}
```

**Correct patterns:**
- Database transactions with row-level locking (SELECT FOR UPDATE)
- Atomic compare-and-swap operations
- Optimistic concurrency with version checks
- Idempotency keys for financial operations

---

### SECURITY_SENSITIVE_EXPOSURE

Sensitive data exposed through logs, error messages, API responses, or other
channels where it should not appear.

**Patterns to flag:**
- PII (names, emails, SSNs, etc.) in logs
- Stack traces with sensitive data returned to users
- Verbose error messages revealing system internals
- API responses including more data than necessary
- Credentials or tokens in URL query strings

**What to look for:**
```
# Sensitive data in errors returned to user
catch (SqlException ex) {
    return BadRequest($"Database error: {ex.Message}");  // Reveals DB details
}

# Over-fetching in API response
return Ok(user);  // Returns entire user object including password hash, internal IDs

# Sensitive data in URLs (gets logged by proxies, browsers)
var url = $"https://api.example.com/auth?token={secretToken}";
```

**Correct patterns:**
- Structured logging with sensitive field redaction
- Generic error messages to users, detailed logs server-side only
- Explicit DTO/projection for API responses
- Sensitive data in headers or POST body, not URL

---

## Review Checklist

When reviewing code that handles:

**User Input:**
- [ ] Input validated/sanitized before use in queries, commands, or expressions
- [ ] Allowlist validation preferred over denylist
- [ ] Input length/format constraints enforced

**Authentication/Authorization:**
- [ ] All endpoints require appropriate authentication
- [ ] Resource access verified against current user's permissions
- [ ] Authorization logic is server-side, not client-controlled

**Secrets:**
- [ ] No hardcoded credentials in source
- [ ] Secrets loaded from secure configuration/environment
- [ ] Logs do not contain sensitive values

**External Requests:**
- [ ] URLs validated against allowlist before fetching
- [ ] Internal network access prevented from user-controlled URLs

**State-Changing Operations:**
- [ ] Critical operations use transactions with appropriate locking
- [ ] Race conditions considered for balance/inventory/permission checks

**Data Exposure:**
- [ ] Error messages do not reveal system internals
- [ ] API responses contain only necessary fields
- [ ] Logs redact sensitive information
