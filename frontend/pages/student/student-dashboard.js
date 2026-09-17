export function renderStudentDashboard(currentUser = null) {

    const studentName =
        currentUser?.name || "Student";

    const registrationNumber =
        currentUser?.identifier || "—";


    return `
        <section class="dashboard-page student-dashboard">

            <div class="dashboard-header">

                <div class="dashboard-header-content">

                    <span class="eyebrow">
                        Student Workspace
                    </span>

                    <h1>
                        Welcome, ${studentName}
                    </h1>

                    <p>
                        Manage your academic applications,
                        track their progress, and access
                        DepartmentAI academic services.
                    </p>

                </div>


                <div class="dashboard-identity">

                    <div class="dashboard-avatar">
                        ${getInitials(studentName)}
                    </div>

                    <div class="dashboard-identity-text">

                        <strong>
                            ${studentName}
                        </strong>

                        <span>
                            ${registrationNumber}
                        </span>

                    </div>

                </div>

            </div>


            <div class="dashboard-section">

                <div class="section-heading">

                    <div>
                        <span class="section-kicker">
                            Overview
                        </span>

                        <h2>
                            Application Status
                        </h2>
                    </div>

                    <span class="section-note">
                        Your current application activity
                    </span>

                </div>


                <div class="dashboard-stat-grid">

                    ${renderStatCard(
                        "Draft",
                        "0",
                        "Applications being prepared",
                        "draft"
                    )}

                    ${renderStatCard(
                        "Submitted",
                        "0",
                        "Applications submitted",
                        "submitted"
                    )}

                    ${renderStatCard(
                        "Under Review",
                        "0",
                        "Applications currently under review",
                        "review"
                    )}

                    ${renderStatCard(
                        "Completed",
                        "0",
                        "Completed application decisions",
                        "completed"
                    )}

                </div>

            </div>


            <div class="dashboard-content-grid">

                <div class="dashboard-panel">

                    <div class="panel-header">

                        <div>
                            <span class="section-kicker">
                                Applications
                            </span>

                            <h2>
                                Recent Applications
                            </h2>
                        </div>

                        <button
                            type="button"
                            class="text-button"
                            data-page="applications"
                        >
                            View all
                            <span>→</span>
                        </button>

                    </div>


                    <div class="dashboard-empty-state">

                        <div class="empty-state-icon">
                            ▣
                        </div>

                        <h3>
                            No applications yet
                        </h3>

                        <p>
                            Applications you create will
                            appear here with their current
                            status and activity.
                        </p>

                        <button
                            type="button"
                            class="primary-button"
                            data-page="create-application"
                        >
                            Create Application
                        </button>

                    </div>

                </div>


                <div class="dashboard-panel">

                    <div class="panel-header">

                        <div>
                            <span class="section-kicker">
                                Services
                            </span>

                            <h2>
                                Quick Actions
                            </h2>
                        </div>

                    </div>


                    <div class="quick-action-list">

                        <button
                            type="button"
                            class="quick-action"
                            data-page="create-application"
                        >

                            <span class="quick-action-icon">
                                +
                            </span>

                            <span class="quick-action-content">

                                <strong>
                                    Create Application
                                </strong>

                                <small>
                                    Start a new academic application
                                </small>

                            </span>

                            <span class="quick-action-arrow">
                                →
                            </span>

                        </button>


                        <button
                            type="button"
                            class="quick-action"
                            data-page="applications"
                        >

                            <span class="quick-action-icon">
                                ▣
                            </span>

                            <span class="quick-action-content">

                                <strong>
                                    My Applications
                                </strong>

                                <small>
                                    View application history and status
                                </small>

                            </span>

                            <span class="quick-action-arrow">
                                →
                            </span>

                        </button>


                        <button
                            type="button"
                            class="quick-action"
                            data-page="assistant"
                        >

                            <span class="quick-action-icon">
                                ✦
                            </span>

                            <span class="quick-action-content">

                                <strong>
                                    Academic Assistant
                                </strong>

                                <small>
                                    Ask questions about academic rules
                                </small>

                            </span>

                            <span class="quick-action-arrow">
                                →
                            </span>

                        </button>

                    </div>

                </div>

            </div>


            <div class="dashboard-info-panel">

                <div class="info-panel-icon">
                    ✦
                </div>

                <div class="info-panel-content">

                    <span class="section-kicker">
                        DepartmentAI Assistant
                    </span>

                    <h3>
                        Need help understanding an academic requirement?
                    </h3>

                    <p>
                        Use the Academic Assistant to ask questions
                        about applicable academic rules and requirements.
                        Responses are based on the department's official
                        knowledge base.
                    </p>

                </div>

                <button
                    type="button"
                    class="secondary-button"
                    data-page="assistant"
                >
                    Open Assistant
                </button>

            </div>

        </section>
    `;
}


function renderStatCard(
    label,
    value,
    description,
    type
) {

    return `
        <div class="dashboard-stat-card">

            <div class="stat-card-top">

                <span class="stat-card-label">
                    ${label}
                </span>

                <span class="stat-card-indicator stat-${type}">
                </span>

            </div>

            <div class="stat-card-value">
                ${value}
            </div>

            <div class="stat-card-description">
                ${description}
            </div>

        </div>
    `;
}


function getInitials(name) {

    if (!name) {
        return "S";
    }


    const parts =
        name
            .trim()
            .split(/\s+/)
            .filter(Boolean);


    if (parts.length === 1) {
        return parts[0]
            .substring(0, 2)
            .toUpperCase();
    }


    return (
        parts[0][0] +
        parts[parts.length - 1][0]
    ).toUpperCase();
}