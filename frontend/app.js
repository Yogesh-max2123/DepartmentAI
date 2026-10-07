import { renderSidebar } from "./components/layout/sidebar.js";
import { renderTopbar } from "./components/layout/topbar.js";

import { renderLoginPage } from "./pages/login/login-page.js";

import { renderStudentLogin } from "./components/auth/student-login.js";
import { renderOfficialLogin } from "./components/auth/official-login.js";
import { renderDUGCLogin } from "./components/auth/dugc-login.js";

import { renderStudentDashboard } from "./pages/student/student-dashboard.js";

import {
    loginUser,
    getCurrentUser,
    logoutUser
} from "./services/auth.js";
const appState = {
    currentUser: getCurrentUser(),
    currentPage: "dashboard",
    selectedLoginRole: null
};


const pageTitles = {
    dashboard: "Dashboard",
    assistant: "Academic Assistant",
    applications: "My Applications",
    "create-application": "Create Application",
    "application-details": "Application Details",
    "application-processing": "Application Processing",
    committee: "Committee Workspace",
    "decision-history": "Decision History",
    audit: "Audit Trail",
    settings: "Settings"
};


/* =========================================================
   Application Initialization
   ========================================================= */

function initializeApp() {

    if (appState.currentUser) {
        renderApplicationShell();
        navigateTo("dashboard");
    } else {
        renderLogin();
    }

}


/* =========================================================
   Login
   ========================================================= */

function renderLogin() {

    const app =
        document.getElementById("app");

    app.innerHTML =
        renderLoginPage();

    setupLoginEvents();

}


function setupLoginEvents() {

    const app =
        document.getElementById("app");

    app.onclick =
        handleLoginClick;

    app.onsubmit =
        handleLoginSubmit;

}


function handleLoginClick(event) {

    const roleButton =
        event.target.closest("[data-login-role]");

    if (roleButton) {

        selectLoginRole(
            roleButton.dataset.loginRole
        );

        return;
    }


    const changeRoleButton =
        event.target.closest("#change-login-role");

    if (changeRoleButton) {

        showRoleSelection();

    }

}


function selectLoginRole(role) {

    appState.selectedLoginRole =
        role;


    const roleSelection =
        document.getElementById(
            "login-role-selection"
        );

    const formContainer =
        document.getElementById(
            "login-form-container"
        );

    const selectedRoleLogin =
        document.getElementById(
            "selected-role-login"
        );


    if (
        !roleSelection ||
        !formContainer ||
        !selectedRoleLogin
    ) {
        return;
    }


    roleSelection.classList.add("hidden");

    formContainer.classList.remove("hidden");


    if (role === "STUDENT") {

        selectedRoleLogin.innerHTML =
            renderStudentLogin();

    } else if (role === "OFFICIAL") {

        selectedRoleLogin.innerHTML =
            renderOfficialLogin();

    } else if (role === "DUGC") {

        selectedRoleLogin.innerHTML =
            renderDUGCLogin();

    }

}


function handleLoginSubmit(event) {

    const form =
        event.target;


    if (!form.classList.contains("role-login-form")) {
        return;
    }


    event.preventDefault();


    const role =
        appState.selectedLoginRole;


    if (!role) {
        return;
    }


    const formData =
        new FormData(form);


    const user =
        loginUser(
            role,
            formData
        );


    if (!user) {

        showLoginError(
            role,
            "Please enter the required information."
        );

        return;
    }


    appState.currentUser =
        user;

    appState.currentPage =
        "dashboard";

    appState.selectedLoginRole =
        null;


    renderApplicationShell();

    setupApplicationEvents();

    navigateTo("dashboard");

}


function showLoginError(role, message) {

    const errorElement =
        document.getElementById(
            `${role.toLowerCase()}-login-error`
        );


    if (!errorElement) {
        return;
    }


    errorElement.textContent =
        message;

    errorElement.classList.remove("hidden");

}


function showRoleSelection() {

    appState.selectedLoginRole =
        null;


    const roleSelection =
        document.getElementById(
            "login-role-selection"
        );

    const formContainer =
        document.getElementById(
            "login-form-container"
        );


    if (
        !roleSelection ||
        !formContainer
    ) {
        return;
    }


    formContainer.classList.add("hidden");

    roleSelection.classList.remove("hidden");


    const selectedRoleLogin =
        document.getElementById(
            "selected-role-login"
        );


    if (selectedRoleLogin) {

        selectedRoleLogin.innerHTML =
            "";

    }

}


/* =========================================================
   Application Shell
   ========================================================= */

function renderApplicationShell() {

    const app =
        document.getElementById("app");


    app.innerHTML = `
        <aside id="sidebar"></aside>

        <div class="main-shell">

            <header id="topbar"></header>

            <main
                id="page-content"
                class="page-content"
            ></main>

        </div>
    `;


    renderShell();

}


function renderShell() {

    const sidebar =
        document.getElementById("sidebar");

    const topbar =
        document.getElementById("topbar");


    if (sidebar) {

        sidebar.innerHTML =
            renderSidebar(
                appState.currentPage,
                appState.currentUser
            );

    }


    if (topbar) {

        topbar.innerHTML =
            renderTopbar(
                appState.currentUser
            );

    }

}


/* =========================================================
   Page Navigation
   ========================================================= */
function navigateTo(page) {

    if (!appState.currentUser) {
        renderLogin();
        return;
    }

    appState.currentPage = page;

    const pageContent =
        document.getElementById("page-content");

    if (!pageContent) {
        return;
    }

    if (
        appState.currentUser.role === "STUDENT"
    ) {
        pageContent.innerHTML =
            renderStudentPage(page);
    } else {
        pageContent.innerHTML =
            renderPlaceholderPage(page);
    }

    updateNavigation();
    updatePageTitle();
}

function renderStudentPage(page) {
    if (page === "dashboard") {
        return renderStudentDashboard(appState.currentUser);
    }

    if (page === "applications") {
        return renderStudentApplicationsPage();
    }

    if (page === "create-application") {
        return renderStudentCreateApplicationPage();
    }

    if (page === "application-details") {
        return renderStudentApplicationDetailsPage();
    }

    if (page === "assistant") {
        return renderStudentAssistantPage();
    }

    if (page === "settings") {
        return renderStudentSettingsPage();
    }

    return renderPlaceholderPage(page);
}

function renderStudentApplicationsPage() {
    return `
        <section class="page-section">
            <div class="page-heading">
                <div>
                    <span class="eyebrow">Student Workspace</span>
                    <h1>My Applications</h1>
                    <p>Track submitted applications, review their current status, and open details when available.</p>
                </div>
            </div>

            <div class="content-panel">
                <div class="empty-state">
                    <div class="empty-state-icon">▣</div>
                    <h3>No applications available to display</h3>
                    <p>The student application list depends on a backend list endpoint that is not currently available. This page is intentionally kept empty until the backend exposes the application list for the logged-in student.</p>
                    <div class="status-block">
                        <strong>Required backend dependency</strong>
                        <span>GET /applications</span>
                    </div>
                    <button type="button" class="primary-button" data-page="create-application">Create Application</button>
                </div>
            </div>
        </section>
    `;
}

function renderStudentCreateApplicationPage() {
    return `
        <section class="page-section">
            <div class="page-heading">
                <div>
                    <span class="eyebrow">Student Workspace</span>
                    <h1>Create Application</h1>
                    <p>Start a new academic application using the DepartmentAI workflow.</p>
                </div>
            </div>

            <div class="content-panel">
                <form class="student-form">
                    <div class="form-grid">
                        <label>
                            <span>Application Type</span>
                            <select>
                                <option>Academic Admission</option>
                                <option>Academic Review</option>
                                <option>Deficiency Correction</option>
                            </select>
                        </label>

                        <label>
                            <span>Application Title</span>
                            <input type="text" placeholder="Enter application title" />
                        </label>
                    </div>

                    <label>
                        <span>Description</span>
                        <textarea rows="6" placeholder="Provide a brief description of the application and purpose."></textarea>
                    </label>

                    <div class="form-actions">
                        <button type="button" class="secondary-button" data-page="applications">Cancel</button>
                        <button type="submit" class="primary-button">Create Application</button>
                    </div>
                </form>
            </div>
        </section>
    `;
}

function renderStudentApplicationDetailsPage() {
    return `
        <section class="page-section">
            <div class="page-heading">
                <div>
                    <span class="eyebrow">Student Workspace</span>
                    <h1>Application Details</h1>
                    <p>Review application status, uploaded documents, requirement checks, and AI-assisted guidance.</p>
                </div>
            </div>

            <div class="content-panel">
                <div class="detail-header">
                    <div>
                        <div class="detail-tag">Application</div>
                        <h3>Application not yet selected</h3>
                    </div>
                    <button type="button" class="secondary-button" data-page="applications">Back to Applications</button>
                </div>

                <div class="detail-list">
                    <div class="detail-item">
                        <span>Status</span>
                        <strong>Not available</strong>
                    </div>
                    <div class="detail-item">
                        <span>Documents</span>
                        <strong>Upload and validation pending</strong>
                    </div>
                    <div class="detail-item">
                        <span>AI-Assisted Analysis</span>
                        <strong>Will appear after processing</strong>
                    </div>
                    <div class="detail-item">
                        <span>Official Decision</span>
                        <strong>Made only by authorized officials</strong>
                    </div>
                </div>
            </div>
        </section>
    `;
}

function renderStudentAssistantPage() {
    return `
        <section class="page-section">
            <div class="page-heading">
                <div>
                    <span class="eyebrow">Academic Services</span>
                    <h1>Academic Assistant</h1>
                    <p>Ask questions about academic rules and requirements using the official DepartmentAI knowledge base.</p>
                </div>
            </div>

            <div class="content-panel assistant-panel">
                <div class="assistant-box">
                    <div class="assistant-box-header">
                        <span class="assistant-badge">AI-Assisted</span>
                    </div>
                    <p>Academic guidance is informational and must be checked against official department requirements and authorized human decisions.</p>
                </div>
                <div class="empty-state compact-empty">
                    <div class="empty-state-icon">✦</div>
                    <h3>Assistant not yet connected</h3>
                    <p>The knowledge-base-backed assistant will be wired into this view once the student-side Q&A flow is connected.</p>
                </div>
            </div>
        </section>
    `;
}

function renderStudentSettingsPage() {
    return `
        <section class="page-section">
            <div class="page-heading">
                <div>
                    <span class="eyebrow">Student Workspace</span>
                    <h1>Settings</h1>
                    <p>Manage your student workspace preferences and account information.</p>
                </div>
            </div>

            <div class="content-panel">
                <div class="empty-state">
                    <div class="empty-state-icon">⚙</div>
                    <h3>Student settings</h3>
                    <p>Profile and preference settings will be added here when the role-specific account configuration is implemented.</p>
                </div>
            </div>
        </section>
    `;
}

/* =========================================================
   Navigation UI
   ========================================================= */

function updateNavigation() {

    document
        .querySelectorAll(".nav-item")
        .forEach(item => {

            item.classList.toggle(
                "active",
                item.dataset.page ===
                appState.currentPage
            );

        });

}


function updatePageTitle() {

    const titleElement =
        document.getElementById(
            "current-page-title"
        );


    if (!titleElement) {
        return;
    }


    titleElement.textContent =
        pageTitles[
            appState.currentPage
        ] || "DepartmentAI";

}


/* =========================================================
   Placeholder Pages
   ========================================================= */

function renderPlaceholderPage(page) {

    const title =
        pageTitles[page] ||
        "DepartmentAI";


    return `
        <section class="page-section">

            <div class="page-heading">

                <div>

                    <span class="eyebrow">
                        DepartmentAI
                    </span>

                    <h1>
                        ${title}
                    </h1>

                    <p>
                        This workspace will be connected
                        to the DepartmentAI application
                        processing system.
                    </p>

                </div>

            </div>


            <div class="content-panel">

                <div class="empty-state">

                    <div class="empty-state-icon">
                        ✦
                    </div>

                    <h3>
                        ${title}
                    </h3>

                    <p>
                        The interface for this module
                        will be implemented in the
                        corresponding role workspace.
                    </p>

                </div>

            </div>

        </section>
    `;

}


/* =========================================================
   Global Application Events
   ========================================================= */

function setupApplicationEvents() {

    const app =
        document.getElementById("app");


    app.onclick =
        handleApplicationClick;

    document.onkeydown =
        handleDocumentKeydown;

}


function handleApplicationClick(event) {

    const navigationTarget =
        event.target.closest("[data-page]");


    if (navigationTarget) {

        event.preventDefault();


        const page =
            navigationTarget.dataset.page;


        if (page) {

            navigateTo(page);

        }

        return;
    }


    const mobileMenuButton =
        event.target.closest(
            "#mobile-menu-button"
        );


    if (mobileMenuButton) {

        const sidebar =
            document.getElementById("sidebar");

        const isOpen =
            sidebar?.classList.toggle("mobile-open");

        mobileMenuButton.setAttribute(
            "aria-expanded",
            String(Boolean(isOpen))
        );

        return;
    }


    const logoutButton =
        event.target.closest(
            "[data-action='logout']"
        );


    if (logoutButton) {

        logout();

    }

    const closeMobileMenuButton =
        event.target.closest(
            "[data-action='close-mobile-menu']"
        );


    if (closeMobileMenuButton) {

        closeMobileMenu();

    }

}


function handleDocumentKeydown(event) {

    if (event.key !== "Escape") {
        return;
    }

    const sidebar =
        document.getElementById("sidebar");

    if (
        sidebar?.classList.contains("mobile-open")
    ) {
        closeMobileMenu();
    }

}


function closeMobileMenu() {

    const sidebar =
        document.getElementById("sidebar");

    const menuButton =
        document.getElementById("mobile-menu-button");

    sidebar?.classList.remove("mobile-open");
    menuButton?.setAttribute("aria-expanded", "false");

}


/* =========================================================
   Logout
   ========================================================= */

function logout() {

    logoutUser();

    appState.currentUser =
        null;

    appState.currentPage =
        "dashboard";

    appState.selectedLoginRole =
        null;


    renderLogin();

}


/* =========================================================
   Start Application
   ========================================================= */

initializeApp();