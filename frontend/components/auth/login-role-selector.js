export function renderLoginRoleSelector(selectedRole = null) {
    const roles = [
        {
            id: "STUDENT",
            title: "Student",
            description: "Sign in to a provisioned Student account",
            icon: "S"
        },
        {
            id: "OFFICIAL",
            title: "Official",
            description: "Sign in to a provisioned Official account",
            icon: "O"
        },
        {
            id: "DUGC",
            title: "DUGC",
            description: "Sign in to a provisioned DUGC account",
            icon: "D"
        }
    ];

    return `
        <div class="login-role-selector">

            <div class="login-role-heading">
                <span class="eyebrow">DepartmentAI</span>
                <h2>Choose your account type</h2>
                <p>
                    The server verifies the account role. This selection cannot grant permissions.
                </p>
            </div>

            <div class="login-role-options">

                ${roles.map(role => `
                    <button
                        type="button"
                        class="login-role-card ${
                            selectedRole === role.id ? "active" : ""
                        }"
                        data-login-role="${role.id}"
                    >

                        <span class="login-role-icon">
                            ${role.icon}
                        </span>

                        <span class="login-role-content">

                            <strong>
                                ${role.title}
                            </strong>

                            <small>
                                ${role.description}
                            </small>

                        </span>

                        <span class="login-role-arrow">
                            →
                        </span>

                    </button>
                `).join("")}

            </div>

        </div>
    `;
}