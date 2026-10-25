export function renderDUGCLogin() {
  return `
    <form id="dugc-login-form" class="role-login-form">
      <div class="form-field">
        <label for="dugc-username">Development account username</label>
        <input id="dugc-username" name="username" type="text" autocomplete="username" required>
      </div>
      <div class="form-field">
        <label for="dugc-password">Password</label>
        <input id="dugc-password" name="password" type="password" autocomplete="current-password" required>
      </div>
      <div id="dugc-login-error" class="login-error hidden" role="alert"></div>
      <button type="submit" class="primary-button login-button">Sign in</button>
    </form>
  `;
}
