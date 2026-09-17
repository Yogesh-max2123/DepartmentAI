export function renderDUGCLogin() {
    return `
        <form id="dugc-login-form" class="role-login-form">

            <div class="form-field">
                <label for="dugc-id">
                    DUGC ID
                </label>

                <input
                    id="dugc-id"
                    name="dugcId"
                    type="text"
                    placeholder="Enter your DUGC ID"
                    autocomplete="username"
                    required
                >
            </div>


            <div class="form-field">
                <label for="dugc-password">
                    Password
                </label>

                <input
                    id="dugc-password"
                    name="password"
                    type="password"
                    placeholder="Enter your password"
                    autocomplete="current-password"
                    required
                >
            </div>


            <div
                id="dugc-login-error"
                class="login-error hidden"
                role="alert"
            ></div>


            <button
                type="submit"
                class="primary-button login-button"
            >
                Sign In
            </button>

        </form>
    `;
}
