export function renderTopbar(currentUser = null) {
    const userName = currentUser?.name || "Department User";
    const userRole = currentUser?.role || "Academic Administration";
    const initials = getInitials(userName);

    return `
        <div class="topbar">

            <div class="topbar-left">

                <button
                    id="mobile-menu-button"
                    class="mobile-menu-button"
                    aria-label="Open navigation"
                >
                    ☰
                </button>

                <div class="breadcrumb">
                    <span>DepartmentAI</span>
                    <span class="breadcrumb-separator">/</span>
                    <strong id="current-page-title">Dashboard</strong>
                </div>

            </div>


            <div class="topbar-right">

                <button
                    class="topbar-action"
                    title="Search"
                    aria-label="Search"
                >
                    ⌕
                </button>

                <button
                    class="topbar-action notification-button"
                    title="Notifications"
                    aria-label="Notifications"
                >
                    ♢
                    <span class="notification-dot"></span>
                </button>

                <div class="user-profile">

                    <div class="user-avatar">
                        ${initials}
                    </div>

                    <div class="user-info">
                        <span class="user-name">${userName}</span>
                        <span class="user-role">${formatRoleLabel(userRole)}</span>
                    </div>

                    <span class="user-chevron">⌄</span>

                </div>

            </div>

        </div>
    `;
}

function getInitials(name) {
    if (!name) {
        return "DU";
    }

    const parts = name.trim().split(/\s+/).filter(Boolean);

    if (parts.length === 1) {
        return parts[0].substring(0, 2).toUpperCase();
    }

    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function formatRoleLabel(role) {
    if (!role) {
        return "Academic Administration";
    }

    const normalized = role.toLowerCase();

    if (normalized === "student") return "Student";
    if (normalized === "official") return "Official";
    if (normalized === "dugc") return "DUGC";

    return role;
}
