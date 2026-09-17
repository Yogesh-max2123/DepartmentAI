export function renderLogin() {
    return `
        <div class="login-page">

            <div class="login-brand">
                <div class="brand-mark">D</div>
                <div>
                    <div class="login-brand-name">DepartmentAI</div>
                    <div class="login-brand-subtitle">
                        Academic Governance Platform
                    </div>
                </div>
            </div>

            <div class="login-card">

                <div class="login-header">
                    <span class="eyebrow">Secure Workspace</span>
                    <h1>Sign in</h1>
                    <p>
                        Select your role to access your DepartmentAI workspace.
                    </p>
                </div>

                <div class="role-selector">

                    <button
                        type="button"
                        class="role-option active"
                        data-login-role="STUDENT"
                    >
                        <span class="role-option-icon">S</span>
                        <span>
                            <strong>Student</strong>
                            <small>Student workspace</small>
                        </span>
                    </button>

                    <button
                        type="button"
                        class="role-option"
                        data-login-role="OFFICIAL"
                    >
                        <span class="role-option-icon">O</span>
                        <span>
                            <strong>Official</strong>
                            <small>Administrative workspace</small>
                        </span>
                    </button>

                    <button
                        type="button"
                        class="role-option"
                        data-login-role="DUGC"
                    >
                        <span class="role-option-icon">D</span>
                        <span>
                            <strong>DUGC</strong>
                            <small>Committee workspace</small>
                        </span>
                    </button>

                </div>

                <form id="login-form" class="login-form">

                    <div id="student-fields">

                        <div class="form-field">
                            <label for="student-name">Student Name</label>
                            <input
                                id="student-name"
                                name="studentName"
                                type="text"
                                placeholder="Enter your name"
                                autocomplete="name"
                            >
                        </div>

                        <div class="form-field">
                            <label for="registration-number">
                                Registration Number
                            </label>
                            <input
                                id="registration-number"
                                name="registrationNumber"
                                type="text"
                                placeholder="Enter registration number"
                                autocomplete="username"
                            >
                        </div>

                    </div>

                    <div id="official-fields" class="hidden">

                        <div class="form-field">
                            <label for="official-name">Official Name</label>
                            <input
                                id="official-name"
                                name="officialName"
                                type="text"
                                placeholder="Enter your name"
                                autocomplete="name"
                            >
                        </div>

                        <div class="form-field">
                            <label for="official-id">Official ID</label>
                            <input
                                id="official-id"
                                name="officialId"
                                type="text"
                                placeholder="Enter official ID"
                                autocomplete="username"
                            >
                        </div>

                    </div>

                    <div id="dugc-fields" class="hidden">

                        <div class="form-field">
                            <label for="dugc-id">DUGC ID</label>
                            <input
                                id="dugc-id"
                                name="dugcId"
                                type="text"
                                placeholder="Enter DUGC ID"
                                autocomplete="username"
                            >
                        </div>

                    </div>

                    <div class="form-field">
                        <label for="login-password">Password</label>

                        <input
                            id="login-password"
                            name="password"
                            type="password"
                            placeholder="Enter your password"
                            autocomplete="current-password"
                        >
                    </div>

                    <div
                        id="login-error"
                        class="login-error hidden"
                        role="alert"
                    ></div>

                    <button type="submit" class="primary-button login-button">
                        Sign In
                    </button>

                </form>

                <div class="login-footer">
                    DepartmentAI · Academic Governance
                </div>

            </div>

        </div>
    `;
}
