import { renderLoginRoleSelector } from "../../components/auth/login-role-selector.js";
import { renderStudentLogin } from "../../components/auth/student-login.js";
import { renderOfficialLogin } from "../../components/auth/official-login.js";
import { renderDUGCLogin } from "../../components/auth/dugc-login.js";


export function renderLoginPage() {
    return `
        <div class="login-page">

            <div class="login-brand">

                <div class="brand-mark">
                    D
                </div>

                <div>
                    <div class="login-brand-name">
                        DepartmentAI
                    </div>

                    <div class="login-brand-subtitle">
                        Academic Governance Platform
                    </div>
                </div>

            </div>


            <div class="login-card">

                <div id="login-role-selection">

                    ${renderLoginRoleSelector()}

                </div>

                <p class="login-prototype-notice" role="note">
                    Development/test accounts only. Local password sign-in is disabled for the institutional profile.
                    Do not enter institutional credentials. Workspace access is determined by the server, not by this selector.
                </p>
                <p id="login-global-message" class="login-error" role="status" hidden></p>

                <div
                    id="login-form-container"
                    class="login-form-container hidden"
                >

                    <button
                        type="button"
                        id="change-login-role"
                        class="login-back-button"
                    >
                        ← Change role
                    </button>


                    <div id="selected-role-login"></div>

                </div>

            </div>


            <div class="login-page-footer">
                DepartmentAI · Academic Governance
            </div>

        </div>
    `;
}