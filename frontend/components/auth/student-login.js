export function renderStudentLogin() {
  return `
    <form id="student-login-form" class="role-login-form">
      <div class="form-field">
        <label for="student-username">Development account username</label>
        <input id="student-username" name="username" type="text" autocomplete="username" required>
      </div>
      <div class="form-field">
        <label for="student-password">Password</label>
        <input id="student-password" name="password" type="password" autocomplete="current-password" required>
      </div>
      <div id="student-login-error" class="login-error hidden" role="alert"></div>
      <button type="submit" class="primary-button login-button">Sign in</button>
    </form>
  `;
}