export function renderStudentLogin() {
    return `
        <form id="student-login-form" class="role-login-form">

            <div class="form-field">
                <label for="student-name">
                    Student Name
                </label>

                <input
                    id="student-name"
                    name="studentName"
                    type="text"
                    placeholder="Enter your full name"
                    autocomplete="name"
                    required
                >
            </div>


            <div class="form-field">
                <label for="student-registration-number">
                    Registration Number
                </label>

                <input
                    id="student-registration-number"
                    name="registrationNumber"
                    type="text"
                    placeholder="Enter your registration number"
                    autocomplete="username"
                    required
                >
            </div>


            <div class="form-field">
                <label for="student-password">
                    Password
                </label>

                <input
                    id="student-password"
                    name="password"
                    type="password"
                    placeholder="Enter your password"
                    autocomplete="current-password"
                    required
                >
            </div>


            <div
                id="student-login-error"
                class="login-error hidden"
                role="alert"
            ></div>


            <button
                type="submit"
                class="primary-button login-button"
            >
                Sign In
            </button>

        </form>
    `;
}