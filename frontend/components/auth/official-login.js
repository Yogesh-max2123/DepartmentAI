export function renderOfficialLogin() {
    return `
        <form id="official-login-form" class="role-login-form">

            <div class="form-field">
                <label for="official-name">
                    Official Name
                </label>

                <input
                    id="official-name"
                    name="officialName"
                    type="text"
                    placeholder="Enter your full name"
                    autocomplete="name"
                    required
                >
            </div>


            <div class="form-field">
                <label for="official-id">
                    Official ID
                </label>

                <input
                    id="official-id"
                    name="officialId"
                    type="text"
                    placeholder="Enter your official ID"
                    autocomplete="username"
                    required
                >
            </div>


            <div class="form-field">
                <label for="official-password">
                    Password
                </label>

                <input
                    id="official-password"
                    name="password"
                    type="password"
                    placeholder="Enter your password"
                    autocomplete="current-password"
                    required
                >
            </div>


            <div
                id="official-login-error"
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