export function renderLoginRoleSelector(selectedRole = null) {
    const roles = [
        {
            id: "STUDENT",
            title: "Student",
            description: "Access applications and academic services",
            icon: "S"
        },
        {
            id: "OFFICIAL",
            title: "Official",
            description: "Manage and process academic applications",
            icon: "O"
        },
        {
            id: "DUGC",
            title: "DUGC",
            description: "Review applications and committee decisions",
            icon: "D"
        }
    ];

    return `
        <div class="login-role-selector">

            <div class="login-role-heading">
                <span class="eyebrow">DepartmentAI</span>
                <h2>Select your role</h2>
                <p>
                    Choose the workspace you want to access.
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