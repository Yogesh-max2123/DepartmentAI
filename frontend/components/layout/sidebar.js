const navigationByRole = {
  STUDENT: [
    {
      section: "Workspace",
      items: [
        {
          page: "dashboard",
          label: "Dashboard",
          icon: "⌂",
        },
        {
          page: "assistant",
          label: "Academic Assistant",
          icon: "✦",
        },
      ],
    },
    {
      section: "Applications",
      items: [
        {
          page: "applications",
          label: "My Applications",
          icon: "▣",
        },
        {
          page: "create-application",
          label: "Create Application",
          icon: "+",
        },
      ],
    },
  ],

  OFFICIAL: [
    {
      section: "Workspace",
      items: [
        {
          page: "dashboard",
          label: "Dashboard",
          icon: "⌂",
        },
        {
          page: "assistant",
          label: "Academic Assistant",
          icon: "✦",
        },
      ],
    },
    {
      section: "Applications",
      items: [
        {
          page: "applications",
          label: "Applications",
          icon: "▣",
        },
        {
          page: "application-processing",
          label: "Application Processing",
          icon: "◈",
        },
      ],
    },
    {
      section: "Governance",
      items: [
        {
          page: "governance-meetings",
          label: "Schedule Meetings",
          icon: "◷",
        },
        {
          page: "committee",
          label: "Committee Workspace",
          icon: "◇",
        },
        {
          page: "audit",
          label: "Audit Trail",
          icon: "◷",
        },
      ],
    },
  ],

  DUGC: [
    {
      section: "Workspace",
      items: [
        {
          page: "dashboard",
          label: "Dashboard",
          icon: "⌂",
        },
        {
          page: "assistant",
          label: "Academic Assistant",
          icon: "✦",
        },
      ],
    },
    {
      section: "Committee",
      items: [
        {
          page: "applications",
          label: "Assigned Applications",
          icon: "▣",
        },
        {
          page: "committee",
          label: "Committee Review",
          icon: "◇",
        },
        {
          page: "decision-history",
          label: "Decision History",
          icon: "◷",
        },
      ],
    },
    {
      section: "Governance",
      items: [
        {
          page: "audit",
          label: "Audit Trail",
          icon: "◈",
        },
      ],
    },
  ],
};

const module2NavigationPermissions = new Set([
  "module2.faculty.read",
  "module2.research.read",
  "module2.research.statistics.read",
  "module2.export.faculty_profiles",
  "module2.export.publications",
]);

export function renderSidebar(
  activePage = "dashboard",
  currentUser = null,
  module2Permissions = [],
) {
  const role = currentUser?.role || "STUDENT";

  const navigation = [
    ...(navigationByRole[role] || navigationByRole.STUDENT),
  ];
  const canAccessModule2 =
    currentUser &&
    Array.isArray(module2Permissions) &&
    module2Permissions.some((permission) =>
      module2NavigationPermissions.has(permission),
    );
  if (canAccessModule2) {
    navigation.push({
      section: "Module II",
      items: [
        {
          page: "module2",
          label: "Faculty & Research",
          icon: "▤",
        },
      ],
    });
  }

  return `
        <div class="sidebar">

            <div class="sidebar-header">

                <div class="sidebar-brand">

                    <div class="brand-mark">
                        D
                    </div>

                <div class="brand-text">

                    <div class="brand-name">
                        DepartmentAI
                    </div>

                    <div class="brand-subtitle">
                        Academic Governance
                    </div>

                </div>

                </div>

                <button
                    type="button"
                    class="sidebar-close-button"
                    data-action="close-mobile-menu"
                    aria-label="Close navigation"
                >
                    ✕
                </button>

            </div>


            <nav class="sidebar-nav">

                ${navigation
                  .map(
                    (group) => `

                    <div class="nav-section-label">
                        ${group.section}
                    </div>

                    ${group.items
                      .map(
                        (item) => `

                        <button
                            type="button"
                            class="nav-item ${
                              activePage === item.page ? "active" : ""
                            }"
                            data-page="${item.page}"
                        >

                            <span class="nav-icon">
                                ${item.icon}
                            </span>

                            <span>
                                ${item.label}
                            </span>

                        </button>

                    `,
                      )
                      .join("")}

                `,
                  )
                  .join("")}

            </nav>


            <div class="sidebar-footer">

                <button
                    type="button"
                    class="nav-item ${
                      activePage === "settings" ? "active" : ""
                    }"
                    data-page="settings"
                >

                    <span class="nav-icon">
                        ⚙
                    </span>

                    <span>
                        Settings
                    </span>

                </button>


                <button
                    type="button"
                    class="nav-item sidebar-logout"
                    data-action="logout"
                >

                    <span class="nav-icon">
                        ↪
                    </span>

                    <span>
                        Sign Out
                    </span>

                </button>


                <div class="sidebar-system-status">

                    <span class="status-dot"></span>

                    <span>
                        Local development
                    </span>

                </div>

            </div>

        </div>
    `;
}
