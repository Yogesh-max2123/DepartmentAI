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