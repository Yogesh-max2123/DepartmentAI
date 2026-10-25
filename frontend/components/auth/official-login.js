export function renderOfficialLogin() {
  return `
    <form id="official-login-form" class="role-login-form">
      <div class="form-field">
        <label for="official-username">Development account username</label>
        <input id="official-username" name="username" type="text" autocomplete="username" required>
      </div>
      <div class="form-field">
        <label for="official-password">Password</label>
        <input id="official-password" name="password" type="password" autocomplete="current-password" required>
      </div>
      <div id="official-login-error" class="login-error hidden" role="alert"></div>
      <button type="submit" class="primary-button login-button">Sign in</button>
    </form>
  `;
}