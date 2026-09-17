export function renderDashboard() {
    return `
        <section class="page-section">

            <div class="page-heading">
                <div>
                    <span class="eyebrow">Overview</span>
                    <h1>Dashboard</h1>
                    <p>
                        Monitor academic applications and governance activities
                        from one place.
                    </p>
                </div>

                <button class="primary-button" data-page="create-application">
                    <span>＋</span>
                    Create Application
                </button>
            </div>


            <div class="stats-grid">

                <div class="stat-card">
                    <div class="stat-card-top">
                        <span class="stat-label">Total Applications</span>
                        <span class="stat-icon">▣</span>
                    </div>

                    <div class="stat-value">—</div>
                    <div class="stat-description">Applications in the system</div>
                </div>


                <div class="stat-card">
                    <div class="stat-card-top">
                        <span class="stat-label">Pending Review</span>
                        <span class="stat-icon">◷</span>
                    </div>

                    <div class="stat-value">—</div>
                    <div class="stat-description">Awaiting academic review</div>
                </div>


                <div class="stat-card">
                    <div class="stat-card-top">
                        <span class="stat-label">Deficiencies</span>
                        <span class="stat-icon">!</span>
                    </div>

                    <div class="stat-value">—</div>
                    <div class="stat-description">Applications requiring attention</div>
                </div>


                <div class="stat-card">
                    <div class="stat-card-top">
                        <span class="stat-label">Committee Reviews</span>
                        <span class="stat-icon">◇</span>
                    </div>

                    <div class="stat-value">—</div>
                    <div class="stat-description">Pending committee actions</div>
                </div>

            </div>


            <div class="dashboard-grid">

                <div class="content-panel large-panel">

                    <div class="panel-header">
                        <div>
                            <h2>Recent Applications</h2>
                            <p>Latest application activity</p>
                        </div>

                        <button
                            class="text-button"
                            data-page="applications"
                        >
                            View all
                        </button>
                    </div>

                    <div class="empty-state">

                        <div class="empty-state-icon">▣</div>

                        <h3>No applications to display</h3>

                        <p>
                            Applications will appear here once they are created.
                        </p>

                    </div>

                </div>


                <div class="content-panel">

                    <div class="panel-header">
                        <div>
                            <h2>System Activity</h2>
                            <p>Recent governance events</p>
                        </div>
                    </div>

                    <div class="empty-state compact">

                        <div class="empty-state-icon">◷</div>

                        <h3>No recent activity</h3>

                        <p>
                            System activity will appear here.
                        </p>

                    </div>

                </div>

            </div>

        </section>
    `;
}